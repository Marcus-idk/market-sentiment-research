"""Validate exact Decimal precision through the storage pipeline."""

from datetime import UTC, datetime
from decimal import Decimal

from data.models import Holdings, PriceData, Session
from data.storage import get_all_holdings, get_price_data_since, store_price_data, upsert_holdings


class TestDecimalPrecision:
    """Exact Decimal precision preservation through storage pipeline"""

    def test_financial_precision_preservation(self, temp_db):
        """Preserves Decimal precision across roundtrip, including edge cases."""
        test_timestamp = datetime(2024, 1, 15, 10, 30, 45, tzinfo=UTC)

        # ========================================
        # EXTREME PRECISION TEST VALUES
        # ========================================
        ultra_precise_price = Decimal("123.456789123456789123")  # 21 decimal places
        ultra_precise_quantity = Decimal("987.654321098765432109")  # 18 decimal places
        ultra_precise_cost = Decimal("121932.631112635269461112")  # Complex calculation result

        # ========================================
        # BOUNDARY CASE VALUES
        # ========================================
        very_small_price = Decimal("0.000000001")  # 9 decimal places
        very_small_quantity = Decimal("0.0000000000001")  # 13 decimal places
        very_small_cost = Decimal("0.00000000000000001")  # 17 decimal places

        # Very large numbers with precision
        very_large_price = Decimal("999999999.999999999")  # Large with 9 decimal places
        very_large_quantity = Decimal("999999999999.999999")  # Even larger with 6 decimal places
        very_large_cost = Decimal("999999999999999.999999999")  # Massive with 9 decimal places

        # ========================================
        # SCIENTIFIC NOTATION EDGE CASES
        # ========================================
        scientific_small = Decimal("1E-15")  # Scientific notation
        scientific_large = Decimal("1.23456789E+12")  # Large scientific

        # ========================================
        # CREATE TEST DATA WITH EXTREME PRECISION VALUES
        # ========================================

        # PriceData with extreme precision testing
        extreme_price_data = [
            PriceData(
                symbol="ULTRA",
                timestamp=test_timestamp,
                price=ultra_precise_price,  # 21 decimal places
                volume=1000000,
                session=Session.REG,
            ),
            PriceData(
                symbol="TINY",
                timestamp=test_timestamp,
                price=very_small_price,  # 9 decimal places - would lose precision as float
                volume=1,
                session=Session.PRE,
            ),
            PriceData(
                symbol="HUGE",
                timestamp=test_timestamp,
                price=very_large_price,  # Large number with 9 decimal precision
                volume=999999999,
                session=Session.POST,
            ),
            PriceData(
                symbol="SCI_SMALL",
                timestamp=test_timestamp,
                price=scientific_small,  # Scientific notation - very small
                volume=1,
                session=Session.REG,
            ),
            PriceData(
                symbol="SCI_LARGE",
                timestamp=test_timestamp,
                price=scientific_large,  # Scientific notation - large
                volume=1,
                session=Session.REG,
            ),
        ]

        # Holdings with extreme precision on all Decimal fields
        extreme_holdings = [
            Holdings(
                symbol="ULTRA",
                quantity=ultra_precise_quantity,  # 18 decimal places
                break_even_price=ultra_precise_price,  # 21 decimal places
                total_cost=ultra_precise_cost,  # Complex precision
                notes="Ultra precision test",
                created_at=test_timestamp,
                updated_at=test_timestamp,
            ),
            Holdings(
                symbol="TINY",
                quantity=very_small_quantity,  # 13 decimal places - critical for fractional shares
                break_even_price=very_small_price,  # 9 decimal places
                total_cost=very_small_cost,  # 17 decimal places - micro-transactions
                notes="Tiny precision boundary test",
                created_at=test_timestamp,
                updated_at=test_timestamp,
            ),
            Holdings(
                symbol="HUGE",
                quantity=very_large_quantity,  # Large with precision
                break_even_price=very_large_price,  # Large with precision
                total_cost=very_large_cost,  # Massive portfolio value
                notes="Large precision boundary test",
                created_at=test_timestamp,
                updated_at=test_timestamp,
            ),
            Holdings(
                symbol="SCI_SMALL",
                quantity=scientific_small,  # Scientific notation quantity
                break_even_price=scientific_small,  # Scientific notation price
                total_cost=Decimal("1E-30"),  # Extremely small total cost
                notes="Scientific notation small test",
                created_at=test_timestamp,
                updated_at=test_timestamp,
            ),
            Holdings(
                symbol="SCI_LARGE",
                quantity=scientific_large,  # Scientific notation quantity
                break_even_price=scientific_large,  # Scientific notation price
                total_cost=Decimal("1.518518518518518518E+24"),  # Scientific notation total
                notes="Scientific notation large test",
                created_at=test_timestamp,
                updated_at=test_timestamp,
            ),
        ]

        # ========================================
        # STORE DATA USING STORAGE FUNCTIONS
        # ========================================

        store_price_data(temp_db, extreme_price_data)

        for holdings in extreme_holdings:
            upsert_holdings(temp_db, holdings)

        # ========================================
        # QUERY DATA BACK
        # ========================================

        retrieved_prices = get_price_data_since(temp_db, datetime(2024, 1, 1, tzinfo=UTC))
        retrieved_holdings = get_all_holdings(temp_db)

        # Verify we got all our test data back
        assert len(retrieved_prices) == 5
        assert len(retrieved_holdings) == 5

        # ========================================
        # VALIDATE EXACT PRECISION PRESERVATION FOR PRICEDATA
        # ========================================

        # Test ultra-precise value
        ultra_price_result = next(item for item in retrieved_prices if item.symbol == "ULTRA")
        ultra_price_stored = ultra_price_result.price
        assert ultra_price_stored == Decimal("123.456789123456789123")

        # Convert back to Decimal and verify exact match
        ultra_price_decimal = ultra_price_stored
        assert ultra_price_decimal == ultra_precise_price

        # Test very small boundary value
        tiny_price_result = next(item for item in retrieved_prices if item.symbol == "TINY")
        tiny_price_stored = tiny_price_result.price
        # Scientific notation may be used for very small numbers
        assert tiny_price_stored in [Decimal("0.000000001"), Decimal("1E-9")]

        # Convert back to Decimal and verify exact match
        tiny_price_decimal = tiny_price_stored
        assert tiny_price_decimal == very_small_price

        # Test very large boundary value
        huge_price_result = next(item for item in retrieved_prices if item.symbol == "HUGE")
        huge_price_stored = huge_price_result.price
        assert huge_price_stored == Decimal("999999999.999999999")

        # Convert back to Decimal and verify exact match
        huge_price_decimal = huge_price_stored
        assert huge_price_decimal == very_large_price

        # Test scientific notation small
        sci_small_result = next(item for item in retrieved_prices if item.symbol == "SCI_SMALL")
        sci_small_stored = sci_small_result.price
        # Scientific notation should be normalized to decimal form
        assert sci_small_stored in [Decimal("0.000000000000001"), Decimal("1E-15")]

        sci_small_decimal = sci_small_stored
        assert sci_small_decimal == scientific_small

        # Test scientific notation large
        sci_large_result = next(item for item in retrieved_prices if item.symbol == "SCI_LARGE")
        sci_large_stored = sci_large_result.price
        # Scientific notation should be normalized to decimal form
        assert sci_large_stored in [Decimal("1234567890000"), Decimal("1.23456789E+12")]

        sci_large_decimal = sci_large_stored
        assert sci_large_decimal == scientific_large

        # ========================================
        # VALIDATE EXACT PRECISION PRESERVATION FOR HOLDINGS
        # ========================================

        # Test ultra-precise holdings
        ultra_holdings_result = next(item for item in retrieved_holdings if item.symbol == "ULTRA")

        # Test quantity precision
        ultra_quantity_stored = ultra_holdings_result.quantity
        assert ultra_quantity_stored == Decimal("987.654321098765432109")
        ultra_quantity_decimal = ultra_quantity_stored
        assert ultra_quantity_decimal == ultra_precise_quantity

        # Test break_even_price precision
        ultra_be_price_stored = ultra_holdings_result.break_even_price
        assert ultra_be_price_stored == Decimal("123.456789123456789123")
        ultra_be_price_decimal = ultra_be_price_stored
        assert ultra_be_price_decimal == ultra_precise_price

        # Test total_cost precision
        ultra_cost_stored = ultra_holdings_result.total_cost
        assert ultra_cost_stored == Decimal("121932.631112635269461112")
        ultra_cost_decimal = ultra_cost_stored
        assert ultra_cost_decimal == ultra_precise_cost

        # Test very small holdings boundary values
        tiny_holdings_result = next(item for item in retrieved_holdings if item.symbol == "TINY")

        tiny_quantity_stored = tiny_holdings_result.quantity
        assert tiny_quantity_stored in [Decimal("0.0000000000001"), Decimal("1E-13")]
        tiny_quantity_decimal = tiny_quantity_stored
        assert tiny_quantity_decimal == very_small_quantity

        tiny_cost_stored = tiny_holdings_result.total_cost
        assert tiny_cost_stored in [Decimal("0.00000000000000001"), Decimal("1E-17")]
        tiny_cost_decimal = tiny_cost_stored
        assert tiny_cost_decimal == very_small_cost

        # Test very large holdings boundary values
        huge_holdings_result = next(item for item in retrieved_holdings if item.symbol == "HUGE")

        huge_quantity_stored = huge_holdings_result.quantity
        assert huge_quantity_stored == Decimal("999999999999.999999")
        huge_quantity_decimal = huge_quantity_stored
        assert huge_quantity_decimal == very_large_quantity

        huge_cost_stored = huge_holdings_result.total_cost
        assert huge_cost_stored == Decimal("999999999999999.999999999")
        huge_cost_decimal = huge_cost_stored
        assert huge_cost_decimal == very_large_cost

        # Test scientific notation holdings
        sci_small_holdings_result = next(
            item for item in retrieved_holdings if item.symbol == "SCI_SMALL"
        )

        # Scientific notation should be preserved as normalized decimal form
        sci_small_quantity_stored = sci_small_holdings_result.quantity
        assert sci_small_quantity_stored in [Decimal("0.000000000000001"), Decimal("1E-15")]
        sci_small_quantity_decimal = sci_small_quantity_stored
        assert sci_small_quantity_decimal == scientific_small

        sci_small_cost_stored = sci_small_holdings_result.total_cost
        # Scientific notation may be used for extremely small numbers
        assert sci_small_cost_stored in [
            Decimal("0.000000000000000000000000000001"),
            Decimal("1E-30"),
        ]
        sci_small_cost_decimal = sci_small_cost_stored
        assert sci_small_cost_decimal == Decimal("1E-30")

        # Test scientific notation large holdings
        sci_large_holdings_result = next(
            item for item in retrieved_holdings if item.symbol == "SCI_LARGE"
        )

        sci_large_quantity_stored = sci_large_holdings_result.quantity
        assert sci_large_quantity_stored in [
            Decimal("1234567890000"),
            Decimal("1.23456789E+12"),
        ]
        sci_large_quantity_decimal = sci_large_quantity_stored
        assert sci_large_quantity_decimal == scientific_large

        sci_large_cost_stored = sci_large_holdings_result.total_cost
        # This is a very large number in scientific notation - should be preserved exactly
        expected_large_cost = (
            "1518518518518518518000000"  # 1.518518518518518518E+24 in decimal form
        )
        assert sci_large_cost_stored in [
            Decimal(expected_large_cost),
            Decimal("1.518518518518518518E+24"),
            Decimal("1.518518518518519E+24"),
        ]
        sci_large_cost_decimal = sci_large_cost_stored
        assert sci_large_cost_decimal == Decimal("1.518518518518518518E+24")

        # ========================================
        # ADDITIONAL VERIFICATION: FLOAT PRECISION LOSS DEMONSTRATION
        # ========================================

        # Convert our ultra-precise value to float and back to show precision loss
        ultra_as_float = float(ultra_precise_price)
        ultra_float_back = Decimal(str(ultra_as_float))

        # Verify that float loses precision (this should be different)
        assert ultra_float_back != ultra_precise_price

        # But our storage preserved it exactly
        assert ultra_price_decimal == ultra_precise_price

        # Test very small number that would underflow to 0 in some contexts
        very_small_as_float = float(very_small_cost)  # 0.00000000000000001
        if very_small_as_float == 0.0:
            # If it underflows to 0, that proves our Decimal storage is superior
            assert tiny_cost_decimal != Decimal("0")
            assert tiny_cost_decimal == very_small_cost
