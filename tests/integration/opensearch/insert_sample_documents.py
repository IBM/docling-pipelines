"""
Sample Document Generator and Inserter for OpenSearch

This script generates realistic sample documents for various document types
(purchase orders, invoices, bank statements, credit card statements, passports)
and inserts them into OpenSearch indexes.
"""

import json
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from faker import Faker
from opensearchpy import OpenSearch, helpers
import argparse


class DocumentGenerator:
    """Generate realistic sample documents for various types"""
    
    def __init__(self, seed: Optional[int] = None):
        """
        Initialize document generator
        
        Args:
            seed: Random seed for reproducible data generation
        """
        self.fake = Faker()
        if seed:
            Faker.seed(seed)
            random.seed(seed)
    
    def generate_purchase_order(self) -> Dict[str, Any]:
        """Generate a sample purchase order"""
        order_date = self.fake.date_time_between(start_date='-1y', end_date='now')
        delivery_date = order_date + timedelta(days=random.randint(7, 30))
        
        num_items = random.randint(1, 5)
        items = []
        total = 0
        
        for _ in range(num_items):
            quantity = random.randint(1, 100)
            unit_price = round(random.uniform(10, 1000), 2)
            item_total = round(quantity * unit_price, 2)
            total += item_total
            
            items.append({
                "item_id": f"ITEM-{self.fake.random_number(digits=6)}",
                "description": self.fake.catch_phrase(),
                "quantity": quantity,
                "unit_price": unit_price,
                "total": item_total
            })
        
        return {
            "po_number": f"PO-{self.fake.year()}-{self.fake.random_number(digits=5)}",
            "order_date": order_date.isoformat(),
            "supplier": {
                "name": self.fake.company(),
                "id": f"SUP-{self.fake.random_number(digits=5)}",
                "contact": self.fake.company_email()
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
                "country": self.fake.country()
            },
            "items": items,
            "payment_terms": "Net 30 days",
            "notes": self.fake.text(max_nb_chars=200)
        }
    
    def generate_invoice(self) -> Dict[str, Any]:
        """Generate a sample invoice"""
        invoice_date = self.fake.date_time_between(start_date='-6m', end_date='now')
        due_date = invoice_date + timedelta(days=30)
        
        num_items = random.randint(1, 8)
        line_items = []
        subtotal = 0
        
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
            
            line_items.append({
                "item_id": f"ITEM-{self.fake.random_number(digits=6)}",
                "description": self.fake.bs(),
                "quantity": quantity,
                "unit_price": unit_price,
                "discount": discount,
                "tax_rate": tax_rate,
                "tax_amount": round(tax_amount, 2),
                "total": round(item_total, 2)
            })
        
        discount_total = sum(item["quantity"] * item["unit_price"] * (item["discount"] / 100) for item in line_items)
        tax_total = sum(item["tax_amount"] for item in line_items)
        total_amount = sum(item["total"] for item in line_items)
        
        payment_status = random.choice(["unpaid", "partial", "paid", "overdue"])
        payment_date = invoice_date + timedelta(days=random.randint(1, 45)) if payment_status in ["paid", "partial"] else None
        
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
                    "country": self.fake.country()
                },
                "tax_id": self.fake.random_number(digits=9),
                "contact": self.fake.company_email()
            },
            "customer": {
                "name": self.fake.company(),
                "id": f"CUST-{self.fake.random_number(digits=5)}",
                "address": {
                    "street": self.fake.street_address(),
                    "city": self.fake.city(),
                    "state": self.fake.state(),
                    "zip": self.fake.zipcode(),
                    "country": self.fake.country()
                },
                "tax_id": self.fake.random_number(digits=9),
                "contact": self.fake.company_email()
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
            "notes": self.fake.text(max_nb_chars=150)
        }
    
    def generate_bank_statement(self) -> Dict[str, Any]:
        """Generate a sample bank statement"""
        end_date = self.fake.date_time_between(start_date='-3m', end_date='now')
        start_date = end_date - timedelta(days=30)
        
        opening_balance = round(random.uniform(1000, 50000), 2)
        current_balance = opening_balance
        
        num_transactions = random.randint(10, 50)
        transactions = []
        
        for i in range(num_transactions):
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
            
            transactions.append({
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
                "check_number": str(self.fake.random_number(digits=4)) if category == "payment" and random.random() > 0.7 else None
            })
        
        closing_balance = current_balance
        total_deposits = sum(t["amount"] for t in transactions if t["type"] == "credit")
        total_withdrawals = sum(t["amount"] for t in transactions if t["type"] == "debit")
        total_fees = sum(t["amount"] for t in transactions if t["type"] == "fee")
        interest_earned = sum(t["amount"] for t in transactions if t["type"] == "interest")
        
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
                    "country": self.fake.country()
                }
            },
            "bank": {
                "name": random.choice(["Chase Bank", "Bank of America", "Wells Fargo", "Citibank", "HDFC Bank"]),
                "branch": f"Branch {self.fake.random_number(digits=4)}",
                "routing_number": str(self.fake.random_number(digits=9)),
                "swift_code": self.fake.swift()
            },
            "account_type": random.choice(["checking", "savings", "business"]),
            "statement_period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
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
            "minimum_balance": round(min(t["balance"] for t in transactions), 2),
            "overdraft_count": sum(1 for t in transactions if t["balance"] < 0),
            "notes": self.fake.text(max_nb_chars=100) if random.random() > 0.7 else None
        }
    
    def generate_credit_card_statement(self) -> Dict[str, Any]:
        """Generate a sample credit card statement"""
        statement_date = self.fake.date_time_between(start_date='-3m', end_date='now')
        start_date = statement_date - timedelta(days=30)
        due_date = statement_date + timedelta(days=21)
        
        previous_balance = round(random.uniform(0, 5000), 2)
        
        num_transactions = random.randint(15, 60)
        transactions = []
        purchases_total = 0
        cash_advances_total = 0
        fees_total = 0
        
        for _ in range(num_transactions):
            trans_date = start_date + timedelta(days=random.randint(0, 30))
            trans_type = random.choice(["purchase"] * 85 + ["payment"] * 10 + ["refund"] * 3 + ["fee"] * 2)
            
            if trans_type == "purchase":
                amount = round(random.uniform(5, 500), 2)
                purchases_total += amount
                category = random.choice(["dining", "groceries", "gas", "travel", "shopping", "entertainment", "utilities"])
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
            
            transactions.append({
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
                    "category_code": str(self.fake.random_number(digits=4))
                },
                "reference": f"REF-{self.fake.random_number(digits=10)}"
            })
        
        payments_credits = sum(abs(t["amount"]) for t in transactions if t["amount"] < 0)
        interest_charged = round(previous_balance * 0.015, 2) if previous_balance > 0 else 0
        new_balance = round(previous_balance + purchases_total + cash_advances_total + fees_total + interest_charged - payments_credits, 2)
        
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
                    "country": self.fake.country()
                }
            },
            "card_issuer": random.choice(["Chase", "American Express", "Citibank", "Capital One", "Discover"]),
            "card_type": random.choice(["Visa", "Mastercard", "Amex", "Discover"]),
            "card_category": random.choice(["personal", "business", "corporate"]),
            "statement_period": {
                "start_date": start_date.isoformat(),
                "end_date": statement_date.isoformat()
            },
            "statement_date": statement_date.isoformat(),
            "payment_due_date": due_date.isoformat(),
            "previous_balance": previous_balance,
            "payments_credits": round(payments_credits, 2),
            "purchases": round(purchases_total, 2),
            "cash_advances": round(cash_advances_total, 2),
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
                "cashback_earned": round(purchases_total * 0.01, 2)
            },
            "apr": {
                "purchases": round(random.uniform(12, 24), 2),
                "cash_advances": round(random.uniform(20, 28), 2),
                "balance_transfers": round(random.uniform(0, 18), 2)
            },
            "late_fee": 0.0,
            "overlimit_fee": 0.0,
            "payment_history": "On time for last 12 months",
            "alerts": None,
            "notes": self.fake.text(max_nb_chars=100) if random.random() > 0.8 else None
        }
    
    def generate_passport(self) -> Dict[str, Any]:
        """Generate a sample passport"""
        issue_date = self.fake.date_time_between(start_date='-10y', end_date='-1y')
        expiry_date = issue_date + timedelta(days=3650)  # 10 years
        dob = self.fake.date_of_birth(minimum_age=18, maximum_age=80)
        
        surname = self.fake.last_name()
        given_names = self.fake.first_name()
        
        num_visas = random.randint(0, 5)
        visas = []
        for _ in range(num_visas):
            visa_issue = self.fake.date_time_between(start_date=issue_date, end_date='now')
            visas.append({
                "visa_number": f"V-{self.fake.random_number(digits=9)}",
                "country": self.fake.country(),
                "type": random.choice(["tourist", "business", "student", "work"]),
                "issue_date": visa_issue.isoformat(),
                "expiry_date": (visa_issue + timedelta(days=random.randint(90, 1825))).isoformat(),
                "entries": random.choice(["single", "multiple"]),
                "duration": f"{random.randint(30, 180)} days",
                "purpose": random.choice(["Tourism", "Business", "Education", "Employment"])
            })
        
        num_stamps = random.randint(0, 15)
        entry_stamps = []
        for _ in range(num_stamps):
            stamp_date = self.fake.date_time_between(start_date=issue_date, end_date='now')
            entry_stamps.append({
                "country": self.fake.country(),
                "port": self.fake.city(),
                "date": stamp_date.isoformat(),
                "type": random.choice(["entry", "exit"]),
                "officer_id": f"OFF-{self.fake.random_number(digits=6)}"
            })
        
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
                    "country": self.fake.country()
                },
                "gender": random.choice(["M", "F"]),
                "height": f"{random.randint(150, 200)} cm",
                "eye_color": random.choice(["Brown", "Blue", "Green", "Hazel", "Gray"]),
                "photo": None,  # Binary data not included in sample
                "signature": None  # Binary data not included in sample
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
                "address": self.fake.address()
            },
            "biometric_data": {
                "fingerprints": None,  # Binary data not included
                "iris_scan": None  # Binary data not included
            },
            "chip_data": None,  # Binary data not included
            "security_features": "Hologram, UV ink, microprinting",
            "status": random.choice(["active", "expired"]) if expiry_date < datetime.now() else "active",
            "previous_passport_number": f"{self.fake.random_letter().upper()}{self.fake.random_number(digits=8)}" if random.random() > 0.7 else None,
            "notes": None
        }


class OpenSearchDocumentInserter:
    """Insert generated documents into OpenSearch"""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 9200,
        use_ssl: bool = False,
        username: Optional[str] = None,
        password: Optional[str] = None
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
            verify_certs=False if not use_ssl else True
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
                body={
                    "settings": {
                        "number_of_shards": 1,
                        "number_of_replicas": 0
                    }
                }
            )
            print(f"Created index: {index_name}")
        else:
            print(f"Index already exists: {index_name}")
    
    def insert_documents(
        self,
        doc_type: str,
        count: int,
        index_name: Optional[str] = None,
        batch_size: int = 100
    ) -> Dict[str, Any]:
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
            "passport": self.generator.generate_passport
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
            for i in range(batch_count):
                doc = generator_func()
                actions.append({
                    "_index": index_name,
                    "_source": doc
                })
            
            # Bulk insert
            try:
                success, errors = helpers.bulk(
                    self.client,
                    actions,
                    raise_on_error=False,
                    raise_on_exception=False
                )
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
            "errors": error_count
        }
        
        print(f"\nInsertion complete:")
        print(f"  - Requested: {count}")
        print(f"  - Succeeded: {success_count}")
        print(f"  - Failed: {error_count}")
        
        return result


def main():
    """Main function with CLI interface"""
    parser = argparse.ArgumentParser(
        description="Generate and insert sample documents into OpenSearch"
    )
    parser.add_argument(
        "--type",
        choices=["purchase_order", "invoice", "bank_statement", "credit_card_statement", "passport", "all"],
        required=True,
        help="Type of document to generate"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of documents to generate (default: 10)"
    )
    parser.add_argument(
        "--index",
        help="Index name (defaults to document type)"
    )
    parser.add_argument(
        "--host",
        default="localhost",
        help="OpenSearch host (default: localhost)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9200,
        help="OpenSearch port (default: 9200)"
    )
    parser.add_argument(
        "--username",
        help="OpenSearch username"
    )
    parser.add_argument(
        "--password",
        help="OpenSearch password"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force recreate index (deletes existing)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Random seed for reproducible data"
    )
    
    args = parser.parse_args()
    
    # Initialize inserter
    inserter = OpenSearchDocumentInserter(
        host=args.host,
        port=args.port,
        username=args.username,
        password=args.password
    )
    
    # Set seed if provided
    if args.seed:
        inserter.generator = DocumentGenerator(seed=args.seed)
    
    # Insert documents
    if args.type == "all":
        doc_types = ["purchase_order", "invoice", "bank_statement", "credit_card_statement", "passport"]
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