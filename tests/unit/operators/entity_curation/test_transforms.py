import unittest

from docpipe.core.operators.functional.entity_curation.transforms import (
    currency_to_numeric,
    make_date_uniform,
    to_number,
    weight_to_numeric,
)


class TestToNumber(unittest.TestCase):
    """Test to_number transformation (multi-language)"""

    def test_numeric_string(self):
        """Test numeric string parsing"""
        result = to_number(number_str="1234")
        self.assertEqual(result, 1234)

    def test_float_string(self):
        """Test float string parsing"""
        result = to_number(number_str="1234.56")
        self.assertAlmostEqual(result, 1234.56, places=2)

    def test_invalid_input(self):
        """Test invalid input returns None"""
        result = to_number(number_str="not a number")
        self.assertIsNone(result)


class TestCurrencyToNumeric(unittest.TestCase):
    """Test currency_to_numeric transformation (locale-aware)"""

    def test_us_locale(self):
        """Test US locale currency parsing"""
        result = currency_to_numeric(amount="$1,234.56", locale="en_US")
        # Returns string, convert to float for comparison
        self.assertAlmostEqual(float(result), 1234.56, places=2)

    def test_de_locale(self):
        """Test German locale currency parsing"""
        result = currency_to_numeric(amount="1.234,56 €", locale="de_DE")
        # Returns string, convert to float for comparison
        self.assertAlmostEqual(float(result), 1234.56, places=2)

    def test_fr_locale(self):
        """Test French locale currency parsing"""
        result = currency_to_numeric(amount="1 234,56 €", locale="fr_FR")
        # Returns string, convert to float for comparison
        self.assertAlmostEqual(float(result), 1234.56, places=2)

    def test_invalid_input(self):
        """Test invalid input returns None"""
        result = currency_to_numeric(amount="invalid", locale="en_US")
        self.assertIsNone(result)


class TestMakeDateUniform(unittest.TestCase):
    """Test make_date_uniform transformation"""

    def test_english_date(self):
        """Test English date parsing"""
        result = make_date_uniform(date_str="March 15, 2024")
        self.assertEqual(result, "2024-03-15")

    def test_french_date(self):
        """Test French month name (parsed by datefinder fallback)"""
        result = make_date_uniform(date_str="15 mars 2024")
        # Datefinder can parse some French dates
        self.assertEqual(result, "2024-03-15")

    def test_numeric_date(self):
        """Test numeric date parsing"""
        result = make_date_uniform(date_str="2024-03-15")
        self.assertEqual(result, "2024-03-15")

    def test_slash_format(self):
        """Test slash-separated date"""
        result = make_date_uniform(date_str="03/15/2024")
        self.assertEqual(result, "2024-03-15")

    def test_invalid_date(self):
        """Test invalid date returns None"""
        result = make_date_uniform(date_str="not a date")
        self.assertIsNone(result)


class TestWeightToNumeric(unittest.TestCase):
    """Test weight_to_numeric transformation (locale-aware)"""

    def test_chinese_jin(self):
        """Test Chinese jin (斤) conversion"""
        result = weight_to_numeric(weight="5斤", locale="zh_CN")
        self.assertAlmostEqual(result, 2.5, places=2)  # 5 * 500g = 2500g = 2.5kg

    def test_japanese_jin(self):
        """Test Japanese jin (斤) conversion"""
        result = weight_to_numeric(weight="5斤", locale="ja_JP")
        self.assertAlmostEqual(result, 3.0, places=2)  # 5 * 600g = 3000g = 3.0kg

    def test_standard_units(self):
        """Test standard weight units"""
        result = weight_to_numeric(weight="5 kg", locale="en_US")
        self.assertAlmostEqual(result, 5.0, places=2)

    def test_pounds(self):
        """Test pounds conversion"""
        result = weight_to_numeric(weight="10 lb", locale="en_US")
        self.assertAlmostEqual(result, 4.536, places=2)

    def test_invalid_input(self):
        """Test invalid input returns None"""
        result = weight_to_numeric(weight="invalid", locale="en_US")
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
