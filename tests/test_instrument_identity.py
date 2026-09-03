import unittest

from rxoptimizer.instrument_identity import canonical_identity,identities_compatible


class InstrumentIdentityTest(unittest.TestCase):
    def test_finger_bass_can_only_map_to_finger_bass(self):
        self.assertTrue(identities_compatible(33,"Finger Bass GM",33,"Finger Bass RX","bass"))
        self.assertFalse(identities_compatible(33,"Finger Bass GM",34,"Picked Bass RX","bass"))

    def test_clean_guitar_rx_address_keeps_clean_identity(self):
        self.assertEqual(canonical_identity(27,"Clean Guitar GM","guitar"),"electric_guitar_clean")
        self.assertEqual(canonical_identity(28,"Clean Guitar RX1","guitar"),"electric_guitar_clean")

    def test_unrelated_instruments_are_rejected(self):
        self.assertFalse(identities_compatible(65,"Alto Sax",71,"Clarinet","melodic"))

    def test_same_address_is_always_preserved(self):
        self.assertTrue(identities_compatible(36,"Unknown",36,"SlapPick Bass RX","bass",same_address=True))


if __name__=="__main__":unittest.main()