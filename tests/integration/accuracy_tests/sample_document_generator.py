"""
Sample Document Generator and Inserter for OpenSearch

This script generates realistic sample documents for various document types
(purchase orders, invoices, bank statements, credit card statements, passports)
and inserts them into OpenSearch indexes.

Extended Features:
- Generate documents in multiple formats (JSON, PDF, HTML, Markdown)
- Export documents to files for testing and validation
"""

import argparse
import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

from faker import Faker
from opensearchpy import OpenSearch, helpers


class DocumentGenerator:
    """Generate realistic sample documents for various types"""

    def __init__(self, seed: int | None = None):
        """
        Initialize document generator

        Args:
            seed: Random seed for reproducible data generation
        """
        self.fake = Faker()
        if seed:
            Faker.seed(seed)
            random.seed(seed)

    def generate_purchase_order(self) -> dict[str, Any]:
        """Generate a sample purchase order"""
        order_date = self.fake.date_time_between(start_date="-1y", end_date="now")
        delivery_date = order_date + timedelta(days=random.randint(7, 30))

        num_items = random.randint(1, 5)
        items = []
        total: float = 0.0

        for _ in range(num_items):
            quantity = random.randint(1, 100)
            unit_price = round(random.uniform(10, 1000), 2)
            item_total = round(quantity * unit_price, 2)
            total += item_total

            items.append(
                {
                    "item_id": f"ITEM-{self.fake.random_number(digits=6)}",
                    "description": self.fake.catch_phrase(),
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "total": item_total,
                }
            )

        return {
            "po_number": f"PO-{self.fake.year()}-{self.fake.random_number(digits=5)}",
            "order_date": order_date.isoformat(),
            "supplier": {
                "name": self.fake.company(),
                "id": f"SUP-{self.fake.random_number(digits=5)}",
                "contact": self.fake.company_email(),
            },
            "department": random.choice(["IT", "Marketing", "Sales", "Operations", "HR", "Finance"]),
            "total_amount": round(total, 2),
            "currency": random.choice(["USD", "EUR", "GBP", "INR"]),
            "status": random.choice(["pending", "approved", "delivered", "cancelled"]),
            "delivery_date": delivery_date.isoformat(),
            "approved_by": self.fake.email(),
            "shipping_address": {
                "street": self.fake.street_address(),
                "city": self.fake.city(),
                "state": self.fake.state(),
                "zip": self.fake.zipcode(),
                "country": self.fake.country(),
            },
            "items": items,
            "payment_terms": "Net 30 days",
            "notes": self.fake.text(max_nb_chars=200),
        }

    def generate_invoice(self) -> dict[str, Any]:
        """Generate a sample invoice"""
        invoice_date = self.fake.date_time_between(start_date="-6m", end_date="now")
        due_date = invoice_date + timedelta(days=30)

        num_items = random.randint(1, 8)
        line_items = []
        subtotal: float = 0.0

        for _ in range(num_items):
            quantity = round(random.uniform(1, 100), 2)
            unit_price = round(random.uniform(10, 500), 2)
            discount = round(random.uniform(0, 10), 2)
            tax_rate = round(random.uniform(5, 15), 2)

            item_subtotal = quantity * unit_price
            discount_amount = item_subtotal * (discount / 100)
            taxable_amount = item_subtotal - discount_amount
            tax_amount = taxable_amount * (tax_rate / 100)
            item_total = taxable_amount + tax_amount

            subtotal += item_subtotal

            line_items.append(
                {
                    "item_id": f"ITEM-{self.fake.random_number(digits=6)}",
                    "description": self.fake.bs(),
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "discount": discount,
                    "tax_rate": tax_rate,
                    "tax_amount": round(tax_amount, 2),
                    "total": round(item_total, 2),
                }
            )

        discount_total = sum(
            cast(float, item["quantity"]) * cast(float, item["unit_price"]) * (cast(float, item["discount"]) / 100)
            for item in line_items
        )
        tax_total = sum(cast(float, item["tax_amount"]) for item in line_items)
        total_amount = sum(cast(float, item["total"]) for item in line_items)

        payment_status = random.choice(["unpaid", "partial", "paid", "overdue"])
        payment_date = (
            invoice_date + timedelta(days=random.randint(1, 45)) if payment_status in ["paid", "partial"] else None
        )

        return {
            "invoice_number": f"INV-{self.fake.year()}-{self.fake.random_number(digits=5)}",
            "invoice_date": invoice_date.isoformat(),
            "due_date": due_date.isoformat(),
            "vendor": {
                "name": self.fake.company(),
                "id": f"VEN-{self.fake.random_number(digits=5)}",
                "address": {
                    "street": self.fake.street_address(),
                    "city": self.fake.city(),
                    "state": self.fake.state(),
                    "zip": self.fake.zipcode(),
                    "country": self.fake.country(),
                },
                "tax_id": self.fake.random_number(digits=9),
                "contact": self.fake.company_email(),
            },
            "customer": {
                "name": self.fake.company(),
                "id": f"CUST-{self.fake.random_number(digits=5)}",
                "address": {
                    "street": self.fake.street_address(),
                    "city": self.fake.city(),
                    "state": self.fake.state(),
                    "zip": self.fake.zipcode(),
                    "country": self.fake.country(),
                },
                "tax_id": self.fake.random_number(digits=9),
                "contact": self.fake.company_email(),
            },
            "line_items": line_items,
            "subtotal": round(subtotal, 2),
            "discount_total": round(discount_total, 2),
            "tax_total": round(tax_total, 2),
            "total_amount": round(total_amount, 2),
            "currency": random.choice(["USD", "EUR", "GBP", "INR"]),
            "payment_status": payment_status,
            "payment_method": random.choice(["wire", "check", "credit_card", "ach"]),
            "payment_date": payment_date.isoformat() if payment_date else None,
            "payment_reference": f"PAY-{self.fake.random_number(digits=8)}" if payment_date else None,
            "po_number": f"PO-{self.fake.year()}-{self.fake.random_number(digits=5)}",
            "terms": "Net 30 days. 2% discount if paid within 10 days.",
            "notes": self.fake.text(max_nb_chars=150),
        }

    def generate_bank_statement(self) -> dict[str, Any]:
        """Generate a sample bank statement"""
        end_date = self.fake.date_time_between(start_date="-3m", end_date="now")
        start_date = end_date - timedelta(days=30)

        opening_balance = round(random.uniform(1000, 50000), 2)
        current_balance = opening_balance

        num_transactions = random.randint(10, 50)
        transactions = []

        for _i in range(num_transactions):
            trans_date = start_date + timedelta(days=random.randint(0, 30))
            trans_type = random.choice(["debit", "credit", "fee", "interest"])

            if trans_type == "credit":
                amount = round(random.uniform(100, 5000), 2)
                current_balance += amount
                category = random.choice(["deposit", "transfer", "refund", "salary"])
            elif trans_type == "fee":
                amount = round(random.uniform(5, 50), 2)
                current_balance -= amount
                category = "fee"
            elif trans_type == "interest":
                amount = round(random.uniform(1, 100), 2)
                current_balance += amount
                category = "interest"
            else:  # debit
                amount = round(random.uniform(10, 2000), 2)
                current_balance -= amount
                category = random.choice(["payment", "withdrawal", "purchase", "transfer"])

            transactions.append(
                {
                    "transaction_id": f"TXN-{self.fake.random_number(digits=10)}",
                    "date": trans_date.isoformat(),
                    "post_date": (trans_date + timedelta(days=random.randint(0, 2))).isoformat(),
                    "description": self.fake.company() if category in ["payment", "purchase"] else self.fake.bs(),
                    "type": trans_type,
                    "category": category,
                    "amount": amount,
                    "balance": round(current_balance, 2),
                    "reference": f"REF-{self.fake.random_number(digits=8)}",
                    "payee": self.fake.name() if trans_type in ["debit", "credit"] else None,
                    "check_number": str(self.fake.random_number(digits=4))
                    if category == "payment" and random.random() > 0.7
                    else None,
                }
            )

        closing_balance = current_balance
        total_deposits = sum(cast(float, t["amount"]) for t in transactions if cast(str, t["type"]) == "credit")
        total_withdrawals = sum(cast(float, t["amount"]) for t in transactions if cast(str, t["type"]) == "debit")
        total_fees = sum(cast(float, t["amount"]) for t in transactions if cast(str, t["type"]) == "fee")
        interest_earned = sum(cast(float, t["amount"]) for t in transactions if cast(str, t["type"]) == "interest")

        return {
            "statement_id": f"STMT-{self.fake.year()}-{self.fake.random_number(digits=6)}",
            "account_number": f"****{self.fake.random_number(digits=4)}",
            "account_holder": {
                "name": self.fake.name(),
                "address": {
                    "street": self.fake.street_address(),
                    "city": self.fake.city(),
                    "state": self.fake.state(),
                    "zip": self.fake.zipcode(),
                    "country": self.fake.country(),
                },
            },
            "bank": {
                "name": random.choice(
                    [
                        "Chase Bank",
                        "Bank of America",
                        "Wells Fargo",
                        "Citibank",
                        "HDFC Bank",
                    ]
                ),
                "branch": f"Branch {self.fake.random_number(digits=4)}",
                "routing_number": str(self.fake.random_number(digits=9)),
                "swift_code": self.fake.swift(),
            },
            "account_type": random.choice(["checking", "savings", "business"]),
            "statement_period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "opening_balance": opening_balance,
            "closing_balance": round(closing_balance, 2),
            "currency": random.choice(["USD", "EUR", "GBP", "INR"]),
            "transactions": sorted(transactions, key=lambda x: x["date"]),
            "total_deposits": round(total_deposits, 2),
            "total_withdrawals": round(total_withdrawals, 2),
            "total_fees": round(total_fees, 2),
            "interest_earned": round(interest_earned, 2),
            "average_balance": round((opening_balance + closing_balance) / 2, 2),
            "minimum_balance": round(min(cast(float, t["balance"]) for t in transactions), 2),
            "overdraft_count": sum(1 for t in transactions if cast(float, t["balance"]) < 0),
            "notes": self.fake.text(max_nb_chars=100) if random.random() > 0.7 else None,
        }

    def generate_credit_card_statement(self) -> dict[str, Any]:
        """Generate a sample credit card statement"""
        statement_date = self.fake.date_time_between(start_date="-3m", end_date="now")
        start_date = statement_date - timedelta(days=30)
        due_date = statement_date + timedelta(days=21)

        previous_balance = round(random.uniform(0, 5000), 2)

        num_transactions = random.randint(15, 60)
        transactions = []
        purchases_total: float = 0.0
        cash_advances_total: float = 0.0
        fees_total: float = 0.0

        for _ in range(num_transactions):
            trans_date = start_date + timedelta(days=random.randint(0, 30))
            trans_type = random.choice(["purchase"] * 85 + ["payment"] * 10 + ["refund"] * 3 + ["fee"] * 2)

            if trans_type == "purchase":
                amount = round(random.uniform(5, 500), 2)
                purchases_total += amount
                category = random.choice(
                    [
                        "dining",
                        "groceries",
                        "gas",
                        "travel",
                        "shopping",
                        "entertainment",
                        "utilities",
                    ]
                )
                merchant_name = self.fake.company()
            elif trans_type == "payment":
                amount = -round(random.uniform(100, 2000), 2)
                category = "payment"
                merchant_name = "Payment - Thank You"
            elif trans_type == "refund":
                amount = -round(random.uniform(10, 200), 2)
                category = "refund"
                merchant_name = self.fake.company()
            else:  # fee
                amount = round(random.uniform(25, 50), 2)
                fees_total += amount
                category = "fee"
                merchant_name = random.choice(["Late Fee", "Over Limit Fee", "Foreign Transaction Fee"])

            foreign_transaction = random.random() > 0.9

            transactions.append(
                {
                    "transaction_id": f"TXN-{self.fake.random_number(digits=12)}",
                    "date": trans_date.isoformat(),
                    "post_date": (trans_date + timedelta(days=random.randint(1, 3))).isoformat(),
                    "description": merchant_name,
                    "category": category,
                    "type": trans_type,
                    "amount": amount,
                    "foreign_amount": round(amount * random.uniform(0.8, 1.2), 2) if foreign_transaction else None,
                    "foreign_currency": random.choice(["EUR", "GBP", "JPY", "CAD"]) if foreign_transaction else None,
                    "exchange_rate": round(random.uniform(0.8, 1.2), 4) if foreign_transaction else None,
                    "merchant": {
                        "name": merchant_name,
                        "city": self.fake.city(),
                        "state": self.fake.state() if random.random() > 0.3 else None,
                        "country": self.fake.country(),
                        "category_code": str(self.fake.random_number(digits=4)),
                    },
                    "reference": f"REF-{self.fake.random_number(digits=10)}",
                }
            )

        payments_credits = sum(abs(cast(float, t["amount"])) for t in transactions if cast(float, t["amount"]) < 0)
        interest_charged = round(previous_balance * 0.015, 2) if previous_balance > 0 else 0
        new_balance = round(
            previous_balance + purchases_total + cash_advances_total + fees_total + interest_charged - payments_credits,
            2,
        )

        credit_limit = round(random.uniform(5000, 50000), 2)
        available_credit = round(credit_limit - new_balance, 2)
        minimum_payment = round(max(25, new_balance * 0.02), 2)

        points_earned = int(purchases_total)  # 1 point per dollar

        return {
            "statement_id": f"CC-STMT-{self.fake.year()}-{self.fake.random_number(digits=6)}",
            "card_number": f"****-****-****-{self.fake.random_number(digits=4)}",
            "cardholder": {
                "name": self.fake.name(),
                "address": {
                    "street": self.fake.street_address(),
                    "city": self.fake.city(),
                    "state": self.fake.state(),
                    "zip": self.fake.zipcode(),
                    "country": self.fake.country(),
                },
            },
            "card_issuer": random.choice(["Chase", "American Express", "Citibank", "Capital One", "Discover"]),
            "card_type": random.choice(["Visa", "Mastercard", "Amex", "Discover"]),
            "card_category": random.choice(["personal", "business", "corporate"]),
            "statement_period": {
                "start_date": start_date.isoformat(),
                "end_date": statement_date.isoformat(),
            },
            "statement_date": statement_date.isoformat(),
            "payment_due_date": due_date.isoformat(),
            "previous_balance": previous_balance,
            "payments_credits": round(payments_credits, 2),
            "purchases": round(purchases_total, 2),
            "cash_advances": cash_advances_total,
            "fees_charged": round(fees_total, 2),
            "interest_charged": interest_charged,
            "new_balance": new_balance,
            "minimum_payment_due": minimum_payment,
            "credit_limit": credit_limit,
            "available_credit": available_credit,
            "currency": "USD",
            "transactions": sorted(transactions, key=lambda x: x["date"]),
            "rewards": {
                "points_earned": points_earned,
                "points_redeemed": random.randint(0, points_earned // 2),
                "points_balance": random.randint(points_earned, points_earned * 3),
                "cashback_earned": round(purchases_total * 0.01, 2),
            },
            "apr": {
                "purchases": round(random.uniform(12, 24), 2),
                "cash_advances": round(random.uniform(20, 28), 2),
                "balance_transfers": round(random.uniform(0, 18), 2),
            },
            "late_fee": 0.0,
            "overlimit_fee": 0.0,
            "payment_history": "On time for last 12 months",
            "alerts": None,
            "notes": self.fake.text(max_nb_chars=100) if random.random() > 0.8 else None,
        }

    def generate_passport(self) -> dict[str, Any]:
        """Generate a sample passport"""
        issue_date = self.fake.date_time_between(start_date="-10y", end_date="-1y")
        expiry_date = issue_date + timedelta(days=3650)  # 10 years
        dob = self.fake.date_of_birth(minimum_age=18, maximum_age=80)

        surname = self.fake.last_name()
        given_names = self.fake.first_name()

        num_visas = random.randint(0, 5)
        visas = []
        for _ in range(num_visas):
            visa_issue = self.fake.date_time_between(start_date=issue_date, end_date="now")
            visas.append(
                {
                    "visa_number": f"V-{self.fake.random_number(digits=9)}",
                    "country": self.fake.country(),
                    "type": random.choice(["tourist", "business", "student", "work"]),
                    "issue_date": visa_issue.isoformat(),
                    "expiry_date": (visa_issue + timedelta(days=random.randint(90, 1825))).isoformat(),
                    "entries": random.choice(["single", "multiple"]),
                    "duration": f"{random.randint(30, 180)} days",
                    "purpose": random.choice(["Tourism", "Business", "Education", "Employment"]),
                }
            )

        num_stamps = random.randint(0, 15)
        entry_stamps = []
        for _ in range(num_stamps):
            stamp_date = self.fake.date_time_between(start_date=issue_date, end_date="now")
            entry_stamps.append(
                {
                    "country": self.fake.country(),
                    "port": self.fake.city(),
                    "date": stamp_date.isoformat(),
                    "type": random.choice(["entry", "exit"]),
                    "officer_id": f"OFF-{self.fake.random_number(digits=6)}",
                }
            )

        return {
            "passport_number": f"{self.fake.random_letter().upper()}{self.fake.random_number(digits=8)}",
            "passport_type": random.choice(["regular", "diplomatic", "official"]),
            "issuing_country": self.fake.country(),
            "issuing_authority": "Department of State",
            "issue_date": issue_date.isoformat(),
            "expiry_date": expiry_date.isoformat(),
            "place_of_issue": self.fake.city(),
            "holder": {
                "surname": surname,
                "given_names": given_names,
                "full_name": f"{given_names} {surname}",
                "nationality": self.fake.country(),
                "date_of_birth": dob.isoformat(),
                "place_of_birth": {
                    "city": self.fake.city(),
                    "state": self.fake.state(),
                    "country": self.fake.country(),
                },
                "gender": random.choice(["M", "F"]),
                "height": f"{random.randint(150, 200)} cm",
                "eye_color": random.choice(["Brown", "Blue", "Green", "Hazel", "Gray"]),
                "photo": None,  # Binary data not included in sample
                "signature": None,  # Binary data not included in sample
            },
            "personal_id_number": str(self.fake.random_number(digits=9)),
            "mrz_line1": f"P<{self.fake.country_code()}{surname}<<{given_names}",
            "mrz_line2": f"{self.fake.random_number(digits=9)}{self.fake.random_number(digits=7)}",
            "mrz_line3": None,
            "document_code": "P",
            "optional_data": None,
            "endorsements": None,
            "visas": visas,
            "entry_stamps": sorted(entry_stamps, key=lambda x: x["date"]),
            "emergency_contact": {
                "name": self.fake.name(),
                "relationship": random.choice(["Spouse", "Parent", "Sibling", "Friend"]),
                "phone": self.fake.phone_number(),
                "address": self.fake.address(),
            },
            "biometric_data": {
                "fingerprints": None,  # Binary data not included
                "iris_scan": None,  # Binary data not included
            },
            "chip_data": None,  # Binary data not included
            "security_features": "Hologram, UV ink, microprinting",
            "status": random.choice(["active", "expired"]) if expiry_date < datetime.now() else "active",
            "previous_passport_number": f"{self.fake.random_letter().upper()}{self.fake.random_number(digits=8)}"
            if random.random() > 0.7
            else None,
            "notes": None,
        }


class DocumentFormatter:
    """Format documents into various output formats (PDF, HTML, Markdown)"""

    @staticmethod
    def to_markdown(doc: dict[str, Any], doc_type: str) -> str:
        """Convert document to Markdown format"""
        if doc_type == "purchase_order":
            return DocumentFormatter._purchase_order_to_markdown(doc)
        elif doc_type == "invoice":
            return DocumentFormatter._invoice_to_markdown(doc)
        elif doc_type == "bank_statement":
            return DocumentFormatter._bank_statement_to_markdown(doc)
        elif doc_type == "credit_card_statement":
            return DocumentFormatter._credit_card_to_markdown(doc)
        elif doc_type == "passport":
            return DocumentFormatter._passport_to_markdown(doc)
        else:
            return f"# {doc_type.upper()}\n\n```json\n{json.dumps(doc, indent=2)}\n```"

    @staticmethod
    def to_html(doc: dict[str, Any], doc_type: str) -> str:
        """Convert document to HTML format"""
        if doc_type == "purchase_order":
            return DocumentFormatter._purchase_order_to_html(doc)
        elif doc_type == "invoice":
            return DocumentFormatter._invoice_to_html(doc)
        elif doc_type == "bank_statement":
            return DocumentFormatter._bank_statement_to_html(doc)
        elif doc_type == "credit_card_statement":
            return DocumentFormatter._credit_card_to_html(doc)
        elif doc_type == "passport":
            return DocumentFormatter._passport_to_html(doc)
        else:
            return f"<html><body><h1>{doc_type.upper()}</h1><pre>{json.dumps(doc, indent=2)}</pre></body></html>"

    @staticmethod
    def to_pdf_content(doc: dict[str, Any], doc_type: str) -> str:
        """
        Generate PDF-ready content (HTML that can be converted to PDF).
        Note: Actual PDF generation requires additional libraries like reportlab or weasyprint.
        This returns HTML that can be converted to PDF using external tools.
        """
        html = DocumentFormatter.to_html(doc, doc_type)
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        h1 {{ color: #333; }}
        h2 {{ color: #666; }}
        .header {{ background-color: #f8f9fa; padding: 20px; margin-bottom: 20px; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 2px solid #333; }}
    </style>
</head>
<body>
{html}
</body>
</html>"""

    @staticmethod
    def _purchase_order_to_markdown(doc: dict[str, Any]) -> str:
        """Convert purchase order to Markdown"""
        md = f"""# Purchase Order: {doc["po_number"]}

## Order Information
- **Order Date**: {doc["order_date"]}
- **Delivery Date**: {doc["delivery_date"]}
- **Status**: {doc["status"]}
- **Department**: {doc["department"]}

## Supplier
- **Name**: {doc["supplier"]["name"]}
- **ID**: {doc["supplier"]["id"]}
- **Contact**: {doc["supplier"]["contact"]}

## Shipping Address
{doc["shipping_address"]["street"]}
{doc["shipping_address"]["city"]}, {doc["shipping_address"]["state"]} {doc["shipping_address"]["zip"]}
{doc["shipping_address"]["country"]}

## Items
| Item ID | Description | Quantity | Unit Price | Total |
|---------|-------------|----------|------------|-------|
"""
        for item in doc["items"]:
            md += f"| {item['item_id']} | {item['description']} | {item['quantity']} | ${item['unit_price']:.2f} | ${item['total']:.2f} |\n"

        md += f"""
## Financial Summary
- **Total Amount**: ${doc["total_amount"]:.2f} {doc["currency"]}
- **Payment Terms**: {doc["payment_terms"]}
- **Approved By**: {doc["approved_by"]}

## Notes
{doc["notes"]}
"""
        return md

    @staticmethod
    def _purchase_order_to_html(doc: dict[str, Any]) -> str:
        """Convert purchase order to HTML"""
        items_html = ""
        for item in doc["items"]:
            items_html += f"""
            <tr>
                <td>{item["item_id"]}</td>
                <td>{item["description"]}</td>
                <td>{item["quantity"]}</td>
                <td>${item["unit_price"]:.2f}</td>
                <td>${item["total"]:.2f}</td>
            </tr>"""

        return f"""
<div class="header">
    <h1>Purchase Order: {doc["po_number"]}</h1>
    <p><strong>Status:</strong> {doc["status"].upper()}</p>
</div>

<h2>Order Information</h2>
<table>
    <tr><th>Order Date</th><td>{doc["order_date"]}</td></tr>
    <tr><th>Delivery Date</th><td>{doc["delivery_date"]}</td></tr>
    <tr><th>Department</th><td>{doc["department"]}</td></tr>
    <tr><th>Approved By</th><td>{doc["approved_by"]}</td></tr>
</table>

<h2>Supplier</h2>
<table>
    <tr><th>Name</th><td>{doc["supplier"]["name"]}</td></tr>
    <tr><th>ID</th><td>{doc["supplier"]["id"]}</td></tr>
    <tr><th>Contact</th><td>{doc["supplier"]["contact"]}</td></tr>
</table>

<h2>Shipping Address</h2>
<p>
{doc["shipping_address"]["street"]}<br>
{doc["shipping_address"]["city"]}, {doc["shipping_address"]["state"]} {doc["shipping_address"]["zip"]}<br>
{doc["shipping_address"]["country"]}
</p>

<h2>Items</h2>
<table>
    <tr>
        <th>Item ID</th>
        <th>Description</th>
        <th>Quantity</th>
        <th>Unit Price</th>
        <th>Total</th>
    </tr>
    {items_html}
</table>

<div class="footer">
    <h2>Financial Summary</h2>
    <p><strong>Total Amount:</strong> ${doc["total_amount"]:.2f} {doc["currency"]}</p>
    <p><strong>Payment Terms:</strong> {doc["payment_terms"]}</p>
    <p><strong>Notes:</strong> {doc["notes"]}</p>
</div>
"""

    @staticmethod
    def _invoice_to_markdown(doc: dict[str, Any]) -> str:
        """Convert invoice to Markdown"""
        md = f"""# Invoice: {doc["invoice_number"]}

## Invoice Information
- **Invoice Date**: {doc["invoice_date"]}
- **Due Date**: {doc["due_date"]}
- **Payment Status**: {doc["payment_status"]}
- **PO Number**: {doc["po_number"]}

## Vendor
- **Name**: {doc["vendor"]["name"]}
- **ID**: {doc["vendor"]["id"]}
- **Contact**: {doc["vendor"]["contact"]}
- **Tax ID**: {doc["vendor"]["tax_id"]}

## Customer
- **Name**: {doc["customer"]["name"]}
- **ID**: {doc["customer"]["id"]}
- **Contact**: {doc["customer"]["contact"]}

## Line Items
| Item ID | Description | Quantity | Unit Price | Discount | Tax | Total |
|---------|-------------|----------|------------|----------|-----|-------|
"""
        for item in doc["line_items"]:
            md += f"| {item['item_id']} | {item['description']} | {item['quantity']:.2f} | ${item['unit_price']:.2f} | {item['discount']:.1f}% | ${item['tax_amount']:.2f} | ${item['total']:.2f} |\n"

        md += f"""
## Financial Summary
- **Subtotal**: ${doc["subtotal"]:.2f}
- **Discount Total**: ${doc["discount_total"]:.2f}
- **Tax Total**: ${doc["tax_total"]:.2f}
- **Total Amount**: ${doc["total_amount"]:.2f} {doc["currency"]}

## Payment Information
- **Payment Method**: {doc["payment_method"]}
- **Payment Date**: {doc["payment_date"] or "Not paid"}
- **Payment Reference**: {doc["payment_reference"] or "N/A"}

## Terms
{doc["terms"]}

## Notes
{doc["notes"]}
"""
        return md

    @staticmethod
    def _invoice_to_html(doc: dict[str, Any]) -> str:
        """Convert invoice to HTML"""
        items_html = ""
        for item in doc["line_items"]:
            items_html += f"""
            <tr>
                <td>{item["item_id"]}</td>
                <td>{item["description"]}</td>
                <td>{item["quantity"]:.2f}</td>
                <td>${item["unit_price"]:.2f}</td>
                <td>{item["discount"]:.1f}%</td>
                <td>${item["tax_amount"]:.2f}</td>
                <td>${item["total"]:.2f}</td>
            </tr>"""

        return f"""
<div class="header">
    <h1>Invoice: {doc["invoice_number"]}</h1>
    <p><strong>Status:</strong> {doc["payment_status"].upper()}</p>
</div>

<h2>Invoice Information</h2>
<table>
    <tr><th>Invoice Date</th><td>{doc["invoice_date"]}</td></tr>
    <tr><th>Due Date</th><td>{doc["due_date"]}</td></tr>
    <tr><th>PO Number</th><td>{doc["po_number"]}</td></tr>
</table>

<h2>Vendor</h2>
<table>
    <tr><th>Name</th><td>{doc["vendor"]["name"]}</td></tr>
    <tr><th>ID</th><td>{doc["vendor"]["id"]}</td></tr>
    <tr><th>Contact</th><td>{doc["vendor"]["contact"]}</td></tr>
</table>

<h2>Line Items</h2>
<table>
    <tr>
        <th>Item ID</th>
        <th>Description</th>
        <th>Quantity</th>
        <th>Unit Price</th>
        <th>Discount</th>
        <th>Tax</th>
        <th>Total</th>
    </tr>
    {items_html}
</table>

<div class="footer">
    <h2>Financial Summary</h2>
    <table>
        <tr><th>Subtotal</th><td>${doc["subtotal"]:.2f}</td></tr>
        <tr><th>Discount</th><td>-${doc["discount_total"]:.2f}</td></tr>
        <tr><th>Tax</th><td>${doc["tax_total"]:.2f}</td></tr>
        <tr><th><strong>Total</strong></th><td><strong>${doc["total_amount"]:.2f} {doc["currency"]}</strong></td></tr>
    </table>
    <p><strong>Payment Terms:</strong> {doc["terms"]}</p>
</div>
"""

    @staticmethod
    def _bank_statement_to_markdown(doc: dict[str, Any]) -> str:
        """Convert bank statement to Markdown"""
        md = f"""# Bank Statement: {doc["statement_id"]}

## Account Information
- **Account Number**: {doc["account_number"]}
- **Account Holder**: {doc["account_holder"]["name"]}
- **Account Type**: {doc["account_type"]}
- **Bank**: {doc["bank"]["name"]} - {doc["bank"]["branch"]}

## Statement Period
- **Start Date**: {doc["statement_period"]["start_date"]}
- **End Date**: {doc["statement_period"]["end_date"]}

## Balance Summary
- **Opening Balance**: ${doc["opening_balance"]:.2f} {doc["currency"]}
- **Closing Balance**: ${doc["closing_balance"]:.2f} {doc["currency"]}
- **Average Balance**: ${doc["average_balance"]:.2f}
- **Minimum Balance**: ${doc["minimum_balance"]:.2f}

## Transaction Summary
- **Total Deposits**: ${doc["total_deposits"]:.2f}
- **Total Withdrawals**: ${doc["total_withdrawals"]:.2f}
- **Total Fees**: ${doc["total_fees"]:.2f}
- **Interest Earned**: ${doc["interest_earned"]:.2f}

## Transactions
| Date | Description | Type | Amount | Balance |
|------|-------------|------|--------|---------|
"""
        for txn in doc["transactions"][:20]:  # Limit to first 20 for readability
            md += f"| {txn['date'][:10]} | {txn['description']} | {txn['type']} | ${txn['amount']:.2f} | ${txn['balance']:.2f} |\n"

        if len(doc["transactions"]) > 20:
            md += f"\n*... and {len(doc['transactions']) - 20} more transactions*\n"

        return md

    @staticmethod
    def _bank_statement_to_html(doc: dict[str, Any]) -> str:
        """Convert bank statement to HTML"""
        txn_html = ""
        for txn in doc["transactions"][:20]:
            txn_html += f"""
            <tr>
                <td>{txn["date"][:10]}</td>
                <td>{txn["description"]}</td>
                <td>{txn["type"]}</td>
                <td>${txn["amount"]:.2f}</td>
                <td>${txn["balance"]:.2f}</td>
            </tr>"""

        return f"""
<div class="header">
    <h1>Bank Statement: {doc["statement_id"]}</h1>
    <p><strong>Account:</strong> {doc["account_number"]}</p>
</div>

<h2>Account Information</h2>
<table>
    <tr><th>Account Holder</th><td>{doc["account_holder"]["name"]}</td></tr>
    <tr><th>Account Type</th><td>{doc["account_type"]}</td></tr>
    <tr><th>Bank</th><td>{doc["bank"]["name"]}</td></tr>
</table>

<h2>Balance Summary</h2>
<table>
    <tr><th>Opening Balance</th><td>${doc["opening_balance"]:.2f}</td></tr>
    <tr><th>Closing Balance</th><td>${doc["closing_balance"]:.2f}</td></tr>
    <tr><th>Total Deposits</th><td>${doc["total_deposits"]:.2f}</td></tr>
    <tr><th>Total Withdrawals</th><td>${doc["total_withdrawals"]:.2f}</td></tr>
</table>

<h2>Transactions</h2>
<table>
    <tr>
        <th>Date</th>
        <th>Description</th>
        <th>Type</th>
        <th>Amount</th>
        <th>Balance</th>
    </tr>
    {txn_html}
</table>
"""

    @staticmethod
    def _credit_card_to_markdown(doc: dict[str, Any]) -> str:
        """Convert credit card statement to Markdown"""
        return f"""# Credit Card Statement: {doc["statement_id"]}

## Card Information
- **Card Number**: {doc["card_number"]}
- **Cardholder**: {doc["cardholder"]["name"]}
- **Card Type**: {doc["card_type"]}
- **Card Issuer**: {doc["card_issuer"]}

## Statement Period
- **Start**: {doc["statement_period"]["start_date"]}
- **End**: {doc["statement_period"]["end_date"]}
- **Due Date**: {doc["payment_due_date"]}

## Balance Summary
- **Previous Balance**: ${doc["previous_balance"]:.2f}
- **Purchases**: ${doc["purchases"]:.2f}
- **Payments/Credits**: ${doc["payments_credits"]:.2f}
- **Fees**: ${doc["fees_charged"]:.2f}
- **Interest**: ${doc["interest_charged"]:.2f}
- **New Balance**: ${doc["new_balance"]:.2f}
- **Minimum Payment**: ${doc["minimum_payment_due"]:.2f}

## Credit Information
- **Credit Limit**: ${doc["credit_limit"]:.2f}
- **Available Credit**: ${doc["available_credit"]:.2f}

## Rewards
- **Points Earned**: {doc["rewards"]["points_earned"]}
- **Cashback Earned**: ${doc["rewards"]["cashback_earned"]:.2f}
"""

    @staticmethod
    def _credit_card_to_html(doc: dict[str, Any]) -> str:
        """Convert credit card statement to HTML"""
        return f"""
<div class="header">
    <h1>Credit Card Statement</h1>
    <p><strong>Card:</strong> {doc["card_number"]}</p>
</div>

<h2>Balance Summary</h2>
<table>
    <tr><th>Previous Balance</th><td>${doc["previous_balance"]:.2f}</td></tr>
    <tr><th>Purchases</th><td>${doc["purchases"]:.2f}</td></tr>
    <tr><th>Payments/Credits</th><td>-${doc["payments_credits"]:.2f}</td></tr>
    <tr><th>New Balance</th><td><strong>${doc["new_balance"]:.2f}</strong></td></tr>
    <tr><th>Minimum Payment Due</th><td>${doc["minimum_payment_due"]:.2f}</td></tr>
    <tr><th>Payment Due Date</th><td>{doc["payment_due_date"]}</td></tr>
</table>
"""

    @staticmethod
    def _passport_to_markdown(doc: dict[str, Any]) -> str:
        """Convert passport to Markdown"""
        return f"""# Passport: {doc["passport_number"]}

## Holder Information
- **Full Name**: {doc["holder"]["full_name"]}
- **Date of Birth**: {doc["holder"]["date_of_birth"]}
- **Nationality**: {doc["holder"]["nationality"]}
- **Gender**: {doc["holder"]["gender"]}

## Passport Details
- **Type**: {doc["passport_type"]}
- **Issuing Country**: {doc["issuing_country"]}
- **Issue Date**: {doc["issue_date"]}
- **Expiry Date**: {doc["expiry_date"]}
- **Status**: {doc["status"]}

## Visas
Total Visas: {len(doc["visas"])}

## Entry Stamps
Total Stamps: {len(doc["entry_stamps"])}
"""

    @staticmethod
    def _passport_to_html(doc: dict[str, Any]) -> str:
        """Convert passport to HTML"""
        return f"""
<div class="header">
    <h1>Passport</h1>
    <p><strong>Number:</strong> {doc["passport_number"]}</p>
</div>

<h2>Holder Information</h2>
<table>
    <tr><th>Full Name</th><td>{doc["holder"]["full_name"]}</td></tr>
    <tr><th>Date of Birth</th><td>{doc["holder"]["date_of_birth"]}</td></tr>
    <tr><th>Nationality</th><td>{doc["holder"]["nationality"]}</td></tr>
    <tr><th>Gender</th><td>{doc["holder"]["gender"]}</td></tr>
</table>

<h2>Passport Details</h2>
<table>
    <tr><th>Type</th><td>{doc["passport_type"]}</td></tr>
    <tr><th>Issuing Country</th><td>{doc["issuing_country"]}</td></tr>
    <tr><th>Issue Date</th><td>{doc["issue_date"]}</td></tr>
    <tr><th>Expiry Date</th><td>{doc["expiry_date"]}</td></tr>
    <tr><th>Status</th><td>{doc["status"]}</td></tr>
</table>
"""


class OpenSearchDocumentInserter:
    """Insert generated documents into OpenSearch"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 9200,
        use_ssl: bool = False,
        username: str | None = None,
        password: str | None = None,
    ):
        """
        Initialize OpenSearch client

        Args:
            host: OpenSearch host
            port: OpenSearch port
            use_ssl: Whether to use SSL
            username: Username for authentication
            password: Password for authentication
        """
        auth = None
        if username and password:
            auth = (username, password)

        self.client = OpenSearch(
            hosts=[{"host": host, "port": port}],
            http_auth=auth,
            http_compress=True,
            use_ssl=use_ssl,
            verify_certs=False if not use_ssl else True,
        )

        self.generator = DocumentGenerator()

    def create_index(self, index_name: str, force: bool = False):
        """
        Create an index with appropriate mappings

        Args:
            index_name: Name of the index to create
            force: If True, delete existing index first
        """
        if force and self.client.indices.exists(index=index_name):
            self.client.indices.delete(index=index_name)
            print(f"Deleted existing index: {index_name}")

        if not self.client.indices.exists(index=index_name):
            # Create index with dynamic mapping
            self.client.indices.create(
                index=index_name,
                body={"settings": {"number_of_shards": 1, "number_of_replicas": 0}},
            )
            print(f"Created index: {index_name}")
        else:
            print(f"Index already exists: {index_name}")

    def insert_documents(
        self,
        doc_type: str,
        count: int,
        index_name: str | None = None,
        batch_size: int = 100,
    ) -> dict[str, Any]:
        """
        Generate and insert documents into OpenSearch

        Args:
            doc_type: Type of document (purchase_order, invoice, bank_statement, credit_card_statement, passport)
            count: Number of documents to generate and insert
            index_name: Index name (defaults to doc_type)
            batch_size: Number of documents to insert per batch

        Returns:
            Dictionary with insertion statistics
        """
        if index_name is None:
            index_name = doc_type

        # Create index if it doesn't exist
        self.create_index(index_name)

        # Map document types to generator methods
        generators = {
            "purchase_order": self.generator.generate_purchase_order,
            "invoice": self.generator.generate_invoice,
            "bank_statement": self.generator.generate_bank_statement,
            "credit_card_statement": self.generator.generate_credit_card_statement,
            "passport": self.generator.generate_passport,
        }

        if doc_type not in generators:
            raise ValueError(f"Unknown document type: {doc_type}. Valid types: {list(generators.keys())}")

        generator_func = generators[doc_type]

        print(f"\nGenerating {count} {doc_type} documents...")

        # Generate and insert in batches
        success_count = 0
        error_count = 0

        for batch_start in range(0, count, batch_size):
            batch_end = min(batch_start + batch_size, count)
            batch_count = batch_end - batch_start

            # Generate batch of documents
            actions = []
            for _i in range(batch_count):
                doc = generator_func()
                actions.append({"_index": index_name, "_source": doc})

            # Bulk insert
            try:
                success, errors = helpers.bulk(self.client, actions, raise_on_error=False, raise_on_exception=False)
                success_count += success
                if errors:
                    error_count += len(errors)
                    print(f"Batch {batch_start}-{batch_end}: {success} succeeded, {len(errors)} failed")
                else:
                    print(f"Batch {batch_start}-{batch_end}: {success} documents inserted")
            except Exception as e:
                print(f"Error inserting batch {batch_start}-{batch_end}: {e}")
                error_count += batch_count

        # Refresh index
        self.client.indices.refresh(index=index_name)

        result = {
            "doc_type": doc_type,
            "index_name": index_name,
            "requested": count,
            "success": success_count,
            "errors": error_count,
        }

        print("\nInsertion complete:")
        print(f"  - Requested: {count}")
        print(f"  - Succeeded: {success_count}")
        print(f"  - Failed: {error_count}")

        return result

    def export_csv(self, doc_type: str, count: int, output_dir: str = "exported_documents") -> dict[str, Any]:
        """
        Generate and export documents to CSV file

        Args:
            doc_type: Type of document to generate
            count: Number of documents to generate
            output_format: Output format (kept for compatibility, always exports as CSV)
            output_dir: Directory to save exported CSV file

        Returns:
            Dictionary with export statistics
        """
        import csv

        # Map document types to generator methods
        generators = {
            "purchase_order": self.generator.generate_purchase_order,
            "invoice": self.generator.generate_invoice,
            "bank_statement": self.generator.generate_bank_statement,
            "credit_card_statement": self.generator.generate_credit_card_statement,
            "passport": self.generator.generate_passport,
        }

        if doc_type not in generators:
            raise ValueError(f"Unknown document type: {doc_type}")

        # Create output directory
        output_path = Path(output_dir) / doc_type
        output_path.mkdir(parents=True, exist_ok=True)

        print(f"\nGenerating {count} {doc_type} documents in CSV format...")
        print(f"Output directory: {output_path}")

        generator_func = generators[doc_type]
        success_count = 0
        error_count = 0

        # Generate filename
        csv_filename = f"{doc_type}_export.csv"
        csv_filepath = output_path / csv_filename

        try:
            # Generate all documents first
            documents = []
            for i in range(count):
                try:
                    doc = generator_func()
                    documents.append(doc)
                    if (i + 1) % 10 == 0:
                        print(f"  Generated {i + 1}/{count} documents...")
                except Exception as e:
                    print(f"  Error generating document {i + 1}: {e}")
                    error_count += 1

            if not documents:
                print("No documents generated successfully")
                return {
                    "doc_type": doc_type,
                    "format": "csv",
                    "output_file": str(csv_filepath),
                    "requested": count,
                    "success": 0,
                    "errors": error_count,
                }

            # Flatten nested dictionaries for CSV export
            def flatten_dict(d, parent_key="", sep="."):
                """Flatten nested dictionary structure"""
                items = []
                for k, v in d.items():
                    new_key = f"{parent_key}{sep}{k}" if parent_key else k
                    if isinstance(v, dict):
                        items.extend(flatten_dict(v, new_key, sep=sep).items())
                    elif isinstance(v, list):
                        # For lists, skip for now
                        # items.append((new_key, json.dumps(v)))
                        pass
                    else:
                        items.append((new_key, v))
                return dict(items)

            # Flatten all documents
            flattened_docs = [flatten_dict(doc) for doc in documents]

            # Get all unique keys across all documents
            all_keys = set()
            for doc in flattened_docs:
                all_keys.update(doc.keys())
            sorted_keys: list[str] = sorted(all_keys)

            # Write to CSV
            with open(csv_filepath, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=sorted_keys)
                writer.writeheader()

                for doc in flattened_docs:
                    # Ensure all keys are present (fill missing with empty string)
                    row = {key: doc.get(key, "") for key in all_keys}
                    writer.writerow(row)
                    success_count += 1

            print("\nCSV export complete:")
            print(f"  - Requested: {count}")
            print(f"  - Succeeded: {success_count}")
            print(f"  - Failed: {error_count}")
            print(f"  - Location: {csv_filepath}")

            return {
                "doc_type": doc_type,
                "format": "csv",
                "output_file": str(csv_filepath),
                "requested": count,
                "success": success_count,
                "errors": error_count,
            }

        except Exception as e:
            print(f"Error writing CSV file: {e}")
            return {
                "doc_type": doc_type,
                "format": "csv",
                "output_file": str(csv_filepath),
                "requested": count,
                "success": success_count,
                "errors": count,
            }

    def export_documents(
        self,
        doc_type: str,
        count: int,
        output_format: str = "json",
        output_dir: str = "exported_documents",
    ) -> dict[str, Any]:
        """
        Generate and export documents to files in specified format

        Args:
            doc_type: Type of document to generate
            count: Number of documents to generate
            output_format: Output format (json, html, markdown, pdf)
            output_dir: Directory to save exported documents

        Returns:
            Dictionary with export statistics
        """
        # Map document types to generator methods
        generators = {
            "purchase_order": self.generator.generate_purchase_order,
            "invoice": self.generator.generate_invoice,
            "bank_statement": self.generator.generate_bank_statement,
            "credit_card_statement": self.generator.generate_credit_card_statement,
            "passport": self.generator.generate_passport,
        }

        if doc_type not in generators:
            raise ValueError(f"Unknown document type: {doc_type}")

        # Create output directory
        output_path = Path(output_dir) / doc_type / output_format
        output_path.mkdir(parents=True, exist_ok=True)

        print(f"\nGenerating {count} {doc_type} documents in {output_format} format...")
        print(f"Output directory: {output_path}")

        generator_func = generators[doc_type]
        success_count = 0
        error_count = 0

        for i in range(count):
            try:
                # Generate document
                doc = generator_func()

                # Determine file extension
                ext_map = {
                    "json": "json",
                    "html": "html",
                    "markdown": "md",
                    "pdf": "html",  # PDF content is HTML that can be converted
                }
                ext = ext_map.get(output_format, "txt")

                # Generate filename
                doc_id = (
                    doc.get("po_number")
                    or doc.get("invoice_number")
                    or doc.get("statement_id")
                    or doc.get("passport_number")
                    or f"doc_{i + 1}"
                )
                filename = f"{doc_id.replace('/', '_')}.{ext}"
                filepath = output_path / filename

                # Format and save document
                if output_format == "json":
                    content = json.dumps(doc, indent=2)
                elif output_format == "html":
                    content = DocumentFormatter.to_html(doc, doc_type)
                elif output_format == "markdown":
                    content = DocumentFormatter.to_markdown(doc, doc_type)
                elif output_format == "pdf":
                    content = DocumentFormatter.to_pdf_content(doc, doc_type)
                else:
                    content = json.dumps(doc, indent=2)

                # Write to file
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)

                success_count += 1
                if (i + 1) % 10 == 0:
                    print(f"  Exported {i + 1}/{count} documents...")

            except Exception as e:
                print(f"  Error exporting document {i + 1}: {e}")
                error_count += 1

        result = {
            "doc_type": doc_type,
            "format": output_format,
            "output_dir": str(output_path),
            "requested": count,
            "success": success_count,
            "errors": error_count,
        }

        print("\nExport complete:")
        print(f"  - Requested: {count}")
        print(f"  - Succeeded: {success_count}")
        print(f"  - Failed: {error_count}")
        print(f"  - Location: {output_path}")

        return result


def main():
    """Main function with CLI interface"""
    parser = argparse.ArgumentParser(description="Generate and insert sample documents into OpenSearch")
    parser.add_argument(
        "--type",
        choices=[
            "purchase_order",
            "invoice",
            "bank_statement",
            "credit_card_statement",
            "passport",
            "all",
        ],
        required=True,
        help="Type of document to generate",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of documents to generate (default: 10)",
    )
    parser.add_argument("--index", help="Index name (defaults to document type)")
    parser.add_argument("--host", default="localhost", help="OpenSearch host (default: localhost)")
    parser.add_argument("--port", type=int, default=9200, help="OpenSearch port (default: 9200)")
    parser.add_argument("--username", help="OpenSearch username")
    parser.add_argument("--password", help="OpenSearch password")
    parser.add_argument("--force", action="store_true", help="Force recreate index (deletes existing)")
    parser.add_argument("--seed", type=int, help="Random seed for reproducible data")
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export documents to files instead of inserting to OpenSearch",
    )
    parser.add_argument(
        "--format",
        choices=["json", "html", "markdown", "pdf"],
        default="json",
        help="Output format for exported documents (default: json)",
    )
    parser.add_argument(
        "--output-dir",
        default="exported_documents",
        help="Output directory for exported documents (default: exported_documents)",
    )
    parser.add_argument("--export-csv", action="store_true", help="Export documents to a CSV file")

    args = parser.parse_args()

    # Initialize inserter
    inserter = OpenSearchDocumentInserter(
        host=args.host, port=args.port, username=args.username, password=args.password
    )

    # Set seed if provided
    if args.seed:
        inserter.generator = DocumentGenerator(seed=args.seed)

    # Export or insert documents
    if args.export_csv:
        # Export documents to CSV file
        if args.type == "all":
            doc_types = [
                "purchase_order",
                "invoice",
                "bank_statement",
                "credit_card_statement",
                "passport",
            ]
            for doc_type in doc_types:
                inserter.export_csv(doc_type, args.count, args.format, args.output_dir)
                print()
        else:
            inserter.export_csv(args.type, args.count, args.format, args.output_dir)
    elif args.export:
        # Export documents to files
        if args.type == "all":
            doc_types = [
                "purchase_order",
                "invoice",
                "bank_statement",
                "credit_card_statement",
                "passport",
            ]
            for doc_type in doc_types:
                inserter.export_documents(doc_type, args.count, args.format, args.output_dir)
                print()
        else:
            inserter.export_documents(args.type, args.count, args.format, args.output_dir)
    else:
        # Insert documents to OpenSearch
        if args.type == "all":
            doc_types = [
                "purchase_order",
                "invoice",
                "bank_statement",
                "credit_card_statement",
                "passport",
            ]
            for doc_type in doc_types:
                index_name = args.index if args.index else doc_type
                if args.force:
                    inserter.create_index(index_name, force=True)
                inserter.insert_documents(doc_type, args.count, index_name)
                print()
        else:
            if args.force:
                index_name = args.index if args.index else args.type
                inserter.create_index(index_name, force=True)
            inserter.insert_documents(args.type, args.count, args.index)


if __name__ == "__main__":
    # Example usage without CLI
    print("=" * 80)
    print("OPENSEARCH SAMPLE DOCUMENT INSERTER")
    print("=" * 80)
    print()
    print("Usage examples:")
    print()
    print("1. Insert 10 purchase orders:")
    print("   python insert_sample_documents.py --type purchase_order --count 10")
    print()
    print("2. Insert 50 invoices into custom index:")
    print("   python insert_sample_documents.py --type invoice --count 50 --index my_invoices")
    print()
    print("3. Insert 100 bank statements with authentication:")
    print("   python insert_sample_documents.py --type bank_statement --count 100 --username admin --password pass")
    print()
    print("4. Insert all document types (10 each):")
    print("   python insert_sample_documents.py --type all --count 10")
    print()
    print("5. Force recreate index and insert documents:")
    print("   python insert_sample_documents.py --type passport --count 20 --force")
    print()
    print("=" * 80)
    print()

    # Run CLI
    main()
