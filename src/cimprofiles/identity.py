import json
import logging
from dataclasses import dataclass, field, is_dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from cimprofiles.env_vars import get_model_authority, get_model_name, get_validation_log_level
from cimprofiles.units.units import CIMUnit

# Global configuration
ARCHIVE_JSON_LD = True
_log = logging.getLogger(__name__)

# Joins the components of a seeded UUID's name. Not whitespace: names often contain spaces.
SEED_SEPARATOR = '+'


def model_authority_namespace(authority: str) -> UUID:
    """
    Returns the UUID namespace (RFC 9562 §6.6) of the identifiers a model authority issues.

    The authority is a URI, as in md:Model.modelingAuthoritySet, so the namespace is
    derived from it with the standard URL namespace: uuid5(NAMESPACE_URL, authority).
    This is also the identifier of the cim:ModelAuthority object itself, so every seeded
    UUID is scoped to its authority the way an RDF namespace scopes its local names.
    """
    return uuid5(NAMESPACE_URL, authority)


def normalize_identifier(value: str) -> str:
    """
    Returns the local part of an rdf:about, rdf:ID or mRID value, so one object gets one
    UUID whichever CIM serialization it was read from. Removes surrounding whitespace,
    a 'urn:uuid:' prefix, everything up to the last '#' (rdf:about="#_x" or a full URI)
    and one leading '_' (552-LEGACY and CGMES rdf:IDs start with '_').
    Case is kept: only UUIDs are case-insensitive.
    """
    value = value.strip().removeprefix('urn:uuid:')
    return value.rpartition('#')[2].removeprefix('_')


def as_uuid(value: str) -> Optional[UUID]:
    """Returns value as a UUID if it is one in any CIM serialization, else None."""
    try:
        return UUID(normalize_identifier(value).lower())
    except ValueError:
        return None


def seeded_uuid(class_name: str, mRID: str = '', name: str = '', seed: str = '') -> UUID:
    """
    Returns the deterministic (version 5) UUID of an object whose identifier is not given
    as a UUID:

        uuid5(model_authority_namespace(authority),
              model + '+' + class_name + '+' + mRID + '+' + name + '+' + seed)

    mRID is normalized (normalize_identifier) and name and seed are whitespace-trimmed.
    Every component keeps its position even when empty, and '%' and '+' inside a
    component are escaped as '%25' and '%2B', so different inputs always give different
    names. Other languages can reproduce these UUIDs from this description alone.
    """
    components = [get_model_name(), class_name, normalize_identifier(mRID), name.strip(),
                  seed.strip()]
    escaped = [component.replace('%', '%25').replace('+', '%2B') for component in components]
    return uuid5(model_authority_namespace(get_model_authority()), SEED_SEPARATOR.join(escaped))


def read_identifier(class_name: str, uri: str) -> UUID:
    """
    Returns the identifier of an object read by its rdf:ID, rdf:about or a reference to it:
    the UUID it contains, else the UUID seeded from it. This is the identifier
    Identity(identifier=uri) gets, so readers can key their graphs by it.
    """
    identifier = as_uuid(uri)
    if identifier is None:
        identifier = seeded_uuid(class_name, uri)
    return identifier


class CIMStereotype(Enum):
    Abstract = 'Abstract'
    Concrete = 'Concrete'
    Description = 'Description'
    Compound = 'Compound'
    AggregateOf = 'AggregateOf'
    OfAggregate = 'OfAggregate'
    Attribute = 'Attribute'
    CIMDatatype = 'CIMDatatype'
    Enumeration = 'Enumeration'
    ByReference = 'ByReference'

def stereotype(stereotype: Enum):
    """
    Decorator to add UML stereotype metadata to dataclasses. Takes any Enum, since
    each generated profile defines its own CIMStereotype (with its custom namespaces).
    """
    def decorator(cls):
        cls.__stereotype__ = stereotype
        return cls
    return decorator

@dataclass(eq=False)
class Identity:
    """
    Base class for CIM 18 identity management.

    This is the root class from CIM 18 to provide common identification
    for all classes needing identification and naming attributes.
    IdentifiedObject is now a child class of Identity.
    mRID is superseded by Identity.identifier, which is typed to be a UUID.

    Equality and hashing use only the identifier: two objects are equal when
    they are the same CIM object, regardless of their other attribute values
    (CIM Joint Issue #7540). Use attribute_utils.diff_attributes to compare
    attribute values. The identifier must not be reassigned after creation,
    otherwise sets and dicts holding the object become inconsistent.
    Generated subclasses must use @dataclass(eq=False) to inherit this.
    """

    identifier: Optional[UUID] = field(
        default=None,
        metadata={
            'type': 'Attribute',
            'minOccurs': '1',
            'maxOccurs': '1',
            'serialize': True
        })

    # True only on objects whose identifier was read as an uppercase UUID (CIMHub and
    # GridAPPS-D data), so uri() reproduces it and database queries still match. Set as an
    # instance attribute only when True, so lowercase and generated identifiers cost nothing.
    _uri_uppercase = False

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Identity):
            return NotImplemented
        return self.identifier == other.identifier

    def __hash__(self) -> int:
        return hash(self.identifier)

    def __post_init__(self) -> None:
        """
        Initializes the UUID after dataclass instantiation.

        Ensures that the identifier field is a valid UUID, creating one from
        other available identification fields if necessary.
        """
        # Cached minimal JSON-LD, so __repr__ stays cheap (debuggers preview whole graphs)
        self.__json_ld__ = None

        # Initialize identifier
        if self.identifier is not None:
            # Handle inheriting from IdentifiedObject with mRID field
            if 'mRID' in self.__dataclass_fields__:
                self.uuid(uri=str(self.identifier),
                         mRID=getattr(self, 'mRID', None),
                         name=getattr(self, 'name', None))
            else:
                self.uuid(uri=str(self.identifier))
        else:
            # Create new identifier
            if 'mRID' in self.__dataclass_fields__:
                self.uuid(mRID=getattr(self, 'mRID', None),
                         name=getattr(self, 'name', None))
            else:
                self.uuid()

    def __str__(self, show_mRID: bool = False, show_empty: bool = False,
                use_names: bool = False) -> str:
        """
        Provides a JSON string representation of the object.

        Args:
            show_mRID: Whether to include mRID and identifier in output
            show_empty: Whether to include empty/None attributes
            use_names: Whether to use names instead of full representation for nested objects

        Returns:
            str: JSON string representation of the object
        """
        # Create JSON-LD dump with repr and all attributes
        dump = dict(json.loads(self.__repr__()) | self.__dict__)

        # Remove internal attributes
        dump.pop('__json_ld__', None)

        # Process each attribute present in the dump (dataclass fields plus any
        # extra instance attributes) so stray values still serialize cleanly.
        # Iterate over a snapshot of the keys because empty attributes get deleted.
        for attribute in list(dump):
            # Skip internal/dunder attributes leaked in via __dict__
            if attribute.startswith('_'):
                del dump[attribute]
                continue

            # Delete attributes that are empty when show_empty is False
            if dump[attribute] is None or dump[attribute] == []:
                if not show_empty:
                    del dump[attribute]
                continue

            # Handle CIM Unit attributes
            elif isinstance(dump[attribute], CIMUnit):
                dump[attribute] = dump[attribute].value

            # Handle dataclass attributes
            if is_dataclass(dump[attribute]):
                if use_names and hasattr(dump[attribute], 'name'):
                    dump[attribute] = dump[attribute].name
                else:
                    dump[attribute] = dump[attribute].__repr__()

            # Convert non-string attributes to strings for JSON compatibility
            elif not isinstance(dump[attribute], str):
                dump[attribute] = str(dump[attribute])

        # Remove identifier and mRID if not showing them
        if not show_mRID:
            dump.pop('identifier', None)
            dump.pop('mRID', None)

        # Convert to JSON with proper formatting
        json_str = json.dumps(dump)

        # Fix common JSON formatting issues
        replacements = [
            ('\\\"', '\"'),
            ('\"[', '['),
            (']\"', ']'),
            ('\"{', '{'),
            ('}\"', '}')
        ]

        for old, new in replacements:
            json_str = json_str.replace(old, new)

        return json_str

    def __repr__(self) -> str:
        """
        Returns a minimal JSON-LD representation of the object.

        Avoids infinite recursion when printing nested objects by providing
        only type and identifier information.

        Returns:
            str: Minimal JSON-LD representation
        """
        if ARCHIVE_JSON_LD and self.__json_ld__ is not None:
            return self.__json_ld__
        return json.dumps({
            '@id': f'{str(self.identifier)}',
            '@type': f'{self.__class__.__name__}'
        })

    def pprint(self, print_mRID: bool = False) -> None:
        """
        Pretty prints the object as formatted JSON.

        Args:
            print_mRID: Whether to include mRID in the output
        """
        print(json.dumps(json.loads(self.__str__(print_mRID)), indent=4))

    def uuid(self, mRID: Optional[str] = None, uri: Optional[str] = None,
             name: Optional[str] = None, seed: Optional[str] = None) -> UUID:
        """
        Creates or updates the object's UUID.

        Read from a file, the identifier (uri) is the UUID and name is not used; one that
        is not a UUID is replaced, with a warning, by a UUID seeded from it, and kept as
        the mRID. Built objects (no uri) are seeded from model, class, mRID, name and seed,
        so a renamed object is a new object with a new UUID.

        Args:
            mRID: An mRID string that might be convertible to a UUID
            uri: A URI string that might be convertible to a UUID
            name: A name to use in seed generation
            seed: Additional seed information for UUID generation

        Returns:
            UUID: The generated or updated UUID
        """
        # Identity.identifier is a UUID (CIM 18): either the one given as the uri (else the
        # mRID) in any serialization, or the seeded uuid5 construct below.
        identifier, source = None, None
        if uri is not None:
            identifier = as_uuid(uri)
            if identifier is not None:
                source = uri
        if identifier is None and mRID is not None:
            identifier = as_uuid(mRID)
            if identifier is not None:
                source = mRID

        if identifier is None:
            # A non-UUID rdf:ID/rdf:about is the object's mRID (when no mRID is given).
            # The class is part of every seeded UUID, so the same mRID or name in two
            # classes gives two different UUIDs.
            key = mRID if mRID is not None else (uri or '')
            if normalize_identifier(key) or (name or '').strip() or (seed or '').strip():
                identifier = seeded_uuid(self.__class__.__name__, key, name or '', seed or '')
            else:
                identifier = uuid4()
        if uri is not None and source != uri:
            _log.log(get_validation_log_level(),
                     f'{self.__class__.__name__} identifier {uri!r} is not a UUID; '
                     f'replaced with {identifier}')
        self.identifier = identifier

        if source is not None and normalize_identifier(source).lower() != normalize_identifier(source):
            self._uri_uppercase = True
        else:
            self.__dict__.pop('_uri_uppercase', None)

        # Update mRID for backwards compatibility
        if 'mRID' in self.__dataclass_fields__:
            if mRID is not None:
                self.mRID = mRID
            elif uri is not None:
                # A UUID uri gives the identifier; a non-UUID uri is kept as the mRID
                # to preserve the original identifier
                self.mRID = self.uri() if source is not None else uri
            else:
                self.mRID = str(identifier)

            # Update name if provided
            if name is not None:
                self.name = name

        # Store JSON-LD representation if configured
        if ARCHIVE_JSON_LD:
            self.__json_ld__ = json.dumps({
                '@id': f'{str(self.identifier)}',
                '@type': f'{self.__class__.__name__}'
            })

        return identifier

    def uri(self) -> str:
        """
        Returns the identifier as text: the UUID, uppercase if it was read uppercase.

        Underscores and 'urn:uuid:' prefixes belong to the serialization style
        (552-NEW, 552-LEGACY, CGMES), so writers add them, not this method.

        Returns:
            str: The UUID string
        """
        uri = str(self.identifier)
        return uri.upper() if self._uri_uppercase else uri

    def to_json(self, show_mRID: bool = True, show_empty: bool = True,
               use_names: bool = False) -> str:
        """
        Returns a JSON string representation of the object.

        Args:
            show_mRID: Whether to include mRID and identifier
            show_empty: Whether to include empty/None attributes
            use_names: Whether to use names instead of full representation for nested objects

        Returns:
            str: JSON string representation
        """
        return self.__str__(
            show_mRID=show_mRID,
            show_empty=show_empty,
            use_names=use_names
        )

    def to_dict(self, show_mRID: bool = True, show_empty: bool = True,
               use_names: bool = False) -> Dict[str, Any]:
        """
        Returns a dictionary representation of the object.

        Args:
            show_mRID: Whether to include mRID and identifier
            show_empty: Whether to include empty/None attributes
            use_names: Whether to use names instead of full representation for nested objects

        Returns:
            Dict[str, Any]: Dictionary representation
        """
        return json.loads(self.__str__(
            show_mRID=show_mRID,
            show_empty=show_empty,
            use_names=use_names
        ))

    def expand(self, max_items: int = 10) -> Dict[str, Any]:
        """
        Expands the Identity object to a dictionary with limited list items.

        Creates a more detailed representation of the object while limiting
        the size of lists to prevent overwhelming output.

        Args:
            max_items: Maximum number of items to include in list fields

        Returns:
            Dict[str, Any]: Expanded dictionary representation
        """
        # Start with the combination of repr() and __dict__
        dump = dict(json.loads(self.__repr__()) | self.__dict__)

        # Remove internal attributes
        dump.pop('__json_ld__', None)

        # Process each attribute present in the dump (dataclass fields plus any
        # extra instance attributes) so stray values still expand cleanly.
        # Iterate over a snapshot of the keys because empty attributes get deleted.
        for attribute in list(dump):
            # Skip internal/dunder attributes leaked in via __dict__
            if attribute.startswith('_'):
                del dump[attribute]
                continue

            value = dump[attribute]

            # Remove empty attributes
            if value is None or value == []:
                dump.pop(attribute, None)
                continue

            # Handle CIM Unit attributes
            elif isinstance(value, CIMUnit):
                dump[attribute] = value.value

            # Handle dataclass values
            elif is_dataclass(value):
                dump[attribute] = json.loads(str(value))
                # Limit any lists within the dataclass
                for k, v in dump[attribute].items():
                    if isinstance(v, list):
                        dump[attribute][k] = v[:max_items]

            # Handle lists - with limit of max_items
            elif isinstance(value, list):
                # Apply item limit
                limited_value = value[:max_items]

                # If list contains dataclasses, expand them too
                if limited_value and all(is_dataclass(item) for item in limited_value):
                    dump[attribute] = [json.loads(str(item)) for item in limited_value]
                else:
                    dump[attribute] = limited_value

            # Convert other types to string
            elif not isinstance(value, str):
                dump[attribute] = str(value)

        return dump
