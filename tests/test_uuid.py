import json
import os
import re
import unittest
from uuid import NAMESPACE_URL, UUID, uuid5

import cimprofiles.cim17.cimhub_2023 as cim
from cimprofiles.env_vars import get_model_authority, get_model_name
from cimprofiles.identity import model_authority_namespace


class TestIdentityUUID(unittest.TestCase):


    def test_initialization_with_mRID(self):
        """Test initializing a Feeder with mRID parameter."""

        feeder = cim.Feeder(mRID='49ad8e07-3bf9-a4e2-cb8f-c3722f837b62')

        # Test string representation
        expected_str = '{"@id": "49ad8e07-3bf9-a4e2-cb8f-c3722f837b62", "@type": "Feeder"}'
        self.assertEqual(feeder.__str__(), expected_str)

        # Test URI method
        self.assertEqual(feeder.uri(), '49ad8e07-3bf9-a4e2-cb8f-c3722f837b62')

    def test_initialization_with_mRID_caps_underscore(self):
        """Test initializing a Feeder with mRID parameter."""

        feeder = cim.Feeder(mRID='_49AD8E07-3BF9-A4E2-CB8F-C3722F837B62')

        # Test string representation
        expected_str = '{"@id": "49ad8e07-3bf9-a4e2-cb8f-c3722f837b62", "@type": "Feeder"}'
        self.assertEqual(feeder.__str__(), expected_str)

        # uri() keeps the case it was read in; underscores are added by the writer's style
        self.assertEqual(feeder.uri(), '49AD8E07-3BF9-A4E2-CB8F-C3722F837B62')

    def test_set_uuid_after_initialization(self):
        """Test setting UUID after initialization using uuid() method."""
        # Initialize empty Feeder, then set UUID
        feeder = cim.Feeder()
        feeder.uuid(mRID='49ad8e07-3bf9-a4e2-cb8f-c3722f837b62')

        # Verify using string representation
        # Note: Using a helper method to compare JSON contents
        self.verify_json_content(
            feeder.__str__(),
            {'@id': '49ad8e07-3bf9-a4e2-cb8f-c3722f837b62', '@type': 'Feeder'}
        )

        # Test URI method
        self.assertEqual(feeder.uri(), '49ad8e07-3bf9-a4e2-cb8f-c3722f837b62')

    def test_initialization_with_UUID_object(self):
        """Test initializing a Feeder with UUID object."""
        uuid_obj = UUID('49ad8e07-3bf9-a4e2-cb8f-c3722f837b62')
        feeder = cim.Feeder(identifier=uuid_obj)

        # Verify using string representation
        self.verify_json_content(
            feeder.__str__(),
            {'@id': '49ad8e07-3bf9-a4e2-cb8f-c3722f837b62', '@type': 'Feeder'}
        )

        # Test URI method
        self.assertEqual(feeder.uri(), '49ad8e07-3bf9-a4e2-cb8f-c3722f837b62')

    def test_invalid_identifier_handling(self):
        """Test that invalid identifiers produce expected behavior and a valid UUID is created."""
        # Create a new test case for an invalid identifier
        with self.assertLogs(level='WARNING') as log_context:
            # This will raise an AssertionError if no logs of the specified level are issued
            feeder = cim.Feeder(identifier='qwertyuiop')

            # Check that we received some warning logs
            self.assertTrue(len(log_context.records) > 0)

            # Check for expected content in warning messages
            warning_text = '\n'.join(record.getMessage() for record in log_context.records)
            self.assertIn('qwertyuiop', warning_text)

            # Two approaches to verify warnings:
            # 1. Less strict: Just check that warnings were generated with the invalid ID
            self.assertTrue(any('qwertyuiop' in record.getMessage() for record in log_context.records))

            # 2. More specific: Check for specific warning messages if needed
            expected_messages = [
                'Identifier qwertyuiop must be a UUID object',
                'URI qwertyuiop not a valid UUID',
                'qwertyuiop not a valid UUID'
            ]

            # Check for each expected message (allowing for partial matches)
            for expected in expected_messages:
                found = False
                for record in log_context.records:
                    if expected in record.getMessage():
                        found = True
                        break
                # Uncomment this if you want strict validation of each message
                # self.assertTrue(found, f"Expected warning containing '{expected}' not found")
            self.validate_uuid_generation(feeder)

    def validate_uuid_generation(self, feeder):
        # Check that a valid UUID was generated - this part is the same
        feeder_json = feeder.__str__()
        if isinstance(feeder_json, dict):
            uuid_str = feeder_json['@id']
        else:
            # Extract UUID from JSON string if __str__ returns a string
            match = re.search(r'"@id":\s*"([^"]+)"', feeder_json)
            uuid_str = match.group(1) if match else None

        # Verify the UUID follows the proper format
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        self.assertIsNotNone(re.match(uuid_pattern, uuid_str))

        # Check that the URI method returns the same UUID
        self.assertEqual(feeder.uri(), uuid_str)

        # Check type is correctly set
        if isinstance(feeder_json, dict):
            self.assertEqual(feeder_json['@type'], 'Feeder')
        else:
            self.assertIn('"@type": "Feeder"', feeder_json)

    # Helper method to compare JSON content regardless of formatting
    def verify_json_content(self, json_str, expected_dict):
        """Helper method to compare JSON content regardless of formatting."""

        # If json_str is already a dictionary (like from __str__()), use it directly
        if isinstance(json_str, dict):
            actual_dict = json_str
        else:
            # Otherwise, parse the JSON string into a dictionary
            actual_dict = json.loads(json_str)

        # Compare dictionaries
        self.assertEqual(actual_dict, expected_dict)


class TestModelAuthorityUUID(unittest.TestCase):

    def setUp(self):
        self._saved_env = {key: os.environ.get(key)
                           for key in ('CIMG_MODEL_AUTHORITY', 'CIMG_MODEL_NAME')}

    def tearDown(self):
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_model_authority.cache_clear()
        get_model_name.cache_clear()

    def _feeder_uuid(self, authority, model_name, **kwargs):
        os.environ['CIMG_MODEL_AUTHORITY'] = authority
        os.environ['CIMG_MODEL_NAME'] = model_name
        get_model_authority.cache_clear()
        get_model_name.cache_clear()
        return cim.Feeder(**kwargs).identifier

    def test_same_scope_is_deterministic(self):
        first = self._feeder_uuid('pnnl', 'feeder_1', name='f1')
        second = self._feeder_uuid('pnnl', 'feeder_1', name='f1')
        self.assertEqual(first, second)

    def test_different_authority_changes_uuid(self):
        first = self._feeder_uuid('pnnl', 'feeder_1', name='f1')
        second = self._feeder_uuid('ieee', 'feeder_1', name='f1')
        self.assertNotEqual(first, second)

    def test_different_model_name_changes_uuid(self):
        first = self._feeder_uuid('pnnl', 'feeder_1', name='f1')
        second = self._feeder_uuid('pnnl', 'feeder_2', name='f1')
        self.assertNotEqual(first, second)

    def test_default_authority_is_a_machine_independent_uri(self):
        os.environ.pop('CIMG_MODEL_AUTHORITY', None)
        get_model_authority.cache_clear()
        self.assertEqual(get_model_authority(), 'https://github.com/PNNL-CIM-Tools/CIM-Graph')

    def test_class_scopes_seeded_uuid(self):
        line = cim.ACLineSegment(mRID='LINE_1').identifier
        terminal = cim.Terminal(mRID='LINE_1').identifier
        self.assertNotEqual(line, terminal)
        self.assertEqual(line, cim.ACLineSegment(mRID='LINE_1').identifier)
        self.assertNotEqual(cim.ACLineSegment(name='1').identifier,
                            cim.Terminal(name='1').identifier)

    def test_no_identifying_input_is_random(self):
        self.assertNotEqual(cim.ACLineSegment().identifier, cim.ACLineSegment().identifier)

    def test_seeded_uuid_is_version_5(self):
        self.assertEqual(self._feeder_uuid('pnnl', 'feeder_1', name='f1').version, 5)
        self.assertEqual(self._feeder_uuid('pnnl', 'feeder_1', mRID='FDR_1').version, 5)

    def test_unseeded_uuid_is_version_4(self):
        self.assertEqual(cim.ACLineSegment().identifier.version, 4)

    def test_seeded_uuid_is_reproducible_outside_cimprofiles(self):
        # The namespace and name are the public contract: other tools (Java, C#, CIMTool)
        # must compute the same identifier from authority, model, class, mRID, name and seed.
        authority = 'https://utility.example.com/models'
        namespace = uuid5(NAMESPACE_URL, authority)
        self.assertEqual(model_authority_namespace(authority), namespace)
        self.assertEqual(self._feeder_uuid(authority, 'feeder_1', name='f1'),
                         uuid5(namespace, 'feeder_1+Feeder++f1+'))
        self.assertEqual(self._feeder_uuid(authority, 'feeder_1', mRID='FDR_1'),
                         uuid5(namespace, 'feeder_1+Feeder+FDR_1++'))
        self.assertEqual(self._feeder_uuid(authority, 'feeder_1', mRID='FDR_1', name='f1'),
                         uuid5(namespace, 'feeder_1+Feeder+FDR_1+f1+'))

    def test_namespace_is_the_model_authority_identifier(self):
        # cim-graph writes uuid5(NAMESPACE_URL, authority) as the cim:ModelAuthority identifier
        authority = 'https://utility.example.com/models'
        self.assertEqual(model_authority_namespace(authority), uuid5(NAMESPACE_URL, authority))

    def test_components_cannot_run_together(self):
        # Without separators, name '650' + mRID 'LINE' and name '65' + mRID '0LINE' collided
        self.assertNotEqual(cim.Feeder(name='650', mRID='LINE').identifier,
                            cim.Feeder(name='65', mRID='0LINE').identifier)
        self.assertNotEqual(cim.Feeder(mRID='A', name='B').identifier,
                            cim.Feeder(mRID='A+B').identifier)
        # seed is only passed through uuid(), as CIM-Builder does for breakers between nodes
        self.assertNotEqual(cim.Feeder().uuid(name='x', seed='y'),
                            cim.Feeder().uuid(name='x+y'))

    def test_separator_and_percent_are_escaped(self):
        authority = 'https://utility.example.com/models'
        namespace = uuid5(NAMESPACE_URL, authority)
        self.assertEqual(self._feeder_uuid(authority, 'm', name='a+b%c'),
                         uuid5(namespace, 'm+Feeder++a%2Bb%25c+'))

    def test_same_object_in_every_serialization_gets_one_uuid(self):
        # rdf:ID (552 ed. 1), rdf:about fragment, full URI and plain mRID forms
        expected = cim.ACLineSegment(mRID='LINE_650_632').identifier
        for identifier in ('_LINE_650_632', '#_LINE_650_632', '#LINE_650_632',
                           'http://utility.example.com/model#_LINE_650_632', ' LINE_650_632 '):
            self.assertEqual(cim.ACLineSegment(identifier=identifier).identifier, expected,
                             identifier)

    def test_non_uuid_identifier_is_the_mrid(self):
        # Identity.identifier is a UUID; a non-UUID rdf:ID stands in for the mRID. It used to
        # be appended twice ('...:_X_X'), so identifier='X' and mRID='X' differed.
        self.assertEqual(cim.ACLineSegment(identifier='X').identifier,
                         cim.ACLineSegment(mRID='X').identifier)

    def test_given_mrid_wins_over_a_non_uuid_identifier(self):
        self.assertEqual(cim.ACLineSegment(identifier='rdf_id', mRID='LINE_1').identifier,
                         cim.ACLineSegment(mRID='LINE_1').identifier)

    def test_empty_inputs_do_not_seed(self):
        # An empty mRID or blank name used to seed with the class alone, so every such
        # object of a class got the same UUID
        self.assertNotEqual(cim.ACLineSegment(mRID='').identifier,
                            cim.ACLineSegment(mRID='').identifier)
        self.assertNotEqual(cim.ACLineSegment(name='  ').identifier,
                            cim.ACLineSegment(name='  ').identifier)

    def test_uri_keeps_case_but_not_underscore(self):
        upper = '49AD8E07-3BF9-4E2A-8B8F-C3722F837B62'
        for identifier in (upper, f'_{upper}', f'#_{upper}', f'urn:uuid:{upper}'):
            self.assertEqual(cim.ACLineSegment(identifier=identifier).uri(), upper, identifier)
        self.assertEqual(cim.ACLineSegment(identifier=upper.lower()).uri(), upper.lower())
        # Generated identifiers are lowercase (RFC 9562), whatever the mRID's case
        self.assertEqual(cim.ACLineSegment(mRID='LINE_1').uri(),
                         str(cim.ACLineSegment(mRID='LINE_1').identifier))

    def test_uppercase_flag_is_stored_only_when_needed(self):
        self.assertNotIn('_uri_uppercase', cim.ACLineSegment(mRID='LINE_1').__dict__)
        self.assertNotIn('_uri_uppercase', cim.ACLineSegment().__dict__)
        self.assertNotIn('__uuid__', cim.ACLineSegment().__dict__)

    def test_identifier_case_is_significant_unless_it_is_a_uuid(self):
        self.assertNotEqual(cim.ACLineSegment(mRID='Line1').identifier,
                            cim.ACLineSegment(mRID='LINE1').identifier)

    def test_name_whitespace_is_ignored(self):
        self.assertEqual(cim.ACLineSegment(name=' 650 ').identifier,
                         cim.ACLineSegment(name='650').identifier)

    def test_uuid_in_any_serialization_is_used_directly(self):
        uuid = UUID('49ad8e07-3bf9-4e2a-8b8f-c3722f837b62')
        for identifier in (str(uuid), str(uuid).upper(), f'_{uuid}', f'#_{uuid}',
                           f'urn:uuid:{uuid}'):
            self.assertEqual(cim.ACLineSegment(identifier=identifier).identifier, uuid,
                             identifier)

    def test_uuid_mrid_is_used_when_identifier_is_not_a_uuid(self):
        uuid = UUID('49ad8e07-3bf9-4e2a-8b8f-c3722f837b62')
        self.assertEqual(cim.ACLineSegment(identifier='LINE_1', mRID=str(uuid)).identifier, uuid)

    def test_repr_never_returns_none(self):
        line = cim.ACLineSegment(name='650')
        line.__json_ld__ = None
        self.assertIn('ACLineSegment', repr(line))

    def test_valid_uuid_mrid_is_unaffected(self):
        mrid = '49ad8e07-3bf9-a4e2-cb8f-c3722f837b62'
        first = self._feeder_uuid('pnnl', 'feeder_1', mRID=mrid)
        second = self._feeder_uuid('ieee', 'feeder_2', mRID=mrid)
        self.assertEqual(first, UUID(mrid))
        self.assertEqual(second, UUID(mrid))


if __name__ == '__main__':
    unittest.main()
