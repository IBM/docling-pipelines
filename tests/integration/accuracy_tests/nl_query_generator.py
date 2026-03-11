"""
Comprehensive Test Query Generator

Generates 100+ natural language test queries with varied complexity levels
for evaluating NL-to-SQL conversion accuracy.

Schema Alignment:
- All queries reference fields from the purchase_orders schema in
  examples/retrieval/document_schemas.json
- Uses "supplier" terminology (not "vendor") to match schema definition
- Field references: supplier.name, supplier.id, department, status,
  total_amount, order_date, delivery_date, etc.
"""

from typing import List, Dict, Any, Optional


class ComprehensiveQueryGenerator:
    """Generate comprehensive test queries with varied complexity"""
    
    def __init__(self):
        """Initialize query generator with test data parameters"""
        self.suppliers = ["ABC Corp", "XYZ Industries", "Tech Solutions Inc", 
                         "Global Supplies Ltd", "Prime Vendors Co"]
        self.departments = ["IT", "Marketing", "Sales", "Operations", "HR", "Finance"]
        self.statuses = ["pending", "approved", "delivered"]
        
    def generate_all_queries(self, complexity_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Generate test queries organized by complexity level
        
        Args:
            complexity_filter: Optional filter to generate only specific complexity level.
                             Valid values: "simple", "filtered", "aggregation", "time_based",
                             "multi_condition", "comparison", "complex", "edge_case"
                             If None, generates all queries.
        
        Returns:
            List of query dictionaries with id, nl_query, expected values, and validators
        
        Examples:
            >>> generator = ComprehensiveQueryGenerator()
            >>> # Get all queries
            >>> all_queries = generator.generate_all_queries()
            >>> # Get only simple queries
            >>> simple_queries = generator.generate_all_queries(complexity_filter="simple")
            >>> # Get only aggregation queries
            >>> agg_queries = generator.generate_all_queries(complexity_filter="aggregation")
        """
        # Define all available query generators
        query_generators = {
            "simple": self._generate_simple_count_queries,
            "filtered": self._generate_filtered_queries,
            "aggregation": self._generate_aggregation_queries,
            "time_based": self._generate_time_based_queries,
            "multi_condition": self._generate_multi_condition_queries,
            "comparison": self._generate_comparison_queries,
            "complex": self._generate_complex_aggregation_queries,
            "edge_case": self._generate_edge_case_queries,
        }
        
        queries: List[Dict[str, Any]] = []
        
        # If filter is specified, generate only that complexity level
        if complexity_filter:
            if complexity_filter not in query_generators:
                valid_filters = ", ".join(query_generators.keys())
                raise ValueError(
                    f"Invalid complexity_filter '{complexity_filter}'. "
                    f"Valid values are: {valid_filters}"
                )
            queries.extend(query_generators[complexity_filter]())
        else:
            # Generate all queries in order
            # Level 1: Simple Count Queries (20 queries)
            queries.extend(self._generate_simple_count_queries())
            
            # Level 2: Filtered Queries (20 queries)
            queries.extend(self._generate_filtered_queries())
            
            # Level 3: Aggregation Queries (20 queries)
            queries.extend(self._generate_aggregation_queries())
            
            # Level 4: Time-based Queries (15 queries)
            queries.extend(self._generate_time_based_queries())
            
            # Level 5: Multi-condition Queries (15 queries)
            queries.extend(self._generate_multi_condition_queries())
            
            # Level 6: Comparison Queries (10 queries)
            queries.extend(self._generate_comparison_queries())
            
            # Level 7: Complex Aggregations (10 queries)
            queries.extend(self._generate_complex_aggregation_queries())
            
            # Level 8: Edge Cases (5 queries)
            queries.extend(self._generate_edge_case_queries())
        
        return queries
    
    def _generate_simple_count_queries(self) -> List[Dict[str, Any]]:
        """Generate simple count queries"""
        queries = []
        
        # Supplier-specific counts
        for i, supplier in enumerate(self.suppliers):
            queries.append({
                "id": f"simple_count_{i+1}_supplier_{supplier.replace(' ', '_').lower()}",
                "nl_query": f"How many orders are from {supplier}?",
                "complexity": "simple",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            })
        
        # Department-specific counts
        for i, dept in enumerate(self.departments):
            queries.append({
                "id": f"simple_count_{i+6}_dept_{dept.lower()}",
                "nl_query": f"Count all orders for {dept} department",
                "complexity": "simple",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            })
        
        # Status-specific counts
        for i, status in enumerate(self.statuses):
            queries.append({
                "id": f"simple_count_{i+12}_status_{status}",
                "nl_query": f"How many {status} orders are there?",
                "complexity": "simple",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            })
        
        # Total count variations
        queries.extend([
            {
                "id": "simple_count_16_total",
                "nl_query": "What is the total number of purchase orders?",
                "complexity": "simple",
                "expected_type": "count",
                "expected_value": 38,
                "validator_type": "exact_count"
            },
            {
                "id": "simple_count_17_all",
                "nl_query": "Count all orders",
                "complexity": "simple",
                "expected_type": "count",
                "expected_value": 38,
                "validator_type": "exact_count"
            },
            {
                "id": "simple_count_18_show_all",
                "nl_query": "Show me all purchase orders",
                "complexity": "simple",
                "expected_type": "count",
                "expected_value": 38,
                "validator_type": "count_any"
            },
            {
                "id": "simple_count_19_list_all",
                "nl_query": "List all orders in the system",
                "complexity": "simple",
                "expected_type": "count",
                "expected_value": 38,
                "validator_type": "count_any"
            },
            {
                "id": "simple_count_20_get_all",
                "nl_query": "Get all purchase orders",
                "complexity": "simple",
                "expected_type": "count",
                "expected_value": 38,
                "validator_type": "count_any"
            }
        ])
        
        return queries
    
    def _generate_filtered_queries(self) -> List[Dict[str, Any]]:
        """Generate filtered queries with single conditions"""
        queries = []
        
        # Amount-based filters
        amount_thresholds = [5000, 10000, 15000, 20000, 25000]
        for i, amount in enumerate(amount_thresholds):
            queries.extend([
                {
                    "id": f"filtered_{i*4+1}_above_{amount}",
                    "nl_query": f"Show orders above ${amount:,}",
                    "complexity": "filtered",
                    "expected_type": "count",
                    "expected_value": "varies",
                    "validator_type": "count_any"
                },
                {
                    "id": f"filtered_{i*4+2}_below_{amount}",
                    "nl_query": f"Find orders below ${amount:,}",
                    "complexity": "filtered",
                    "expected_type": "count",
                    "expected_value": "varies",
                    "validator_type": "count_any"
                },
                {
                    "id": f"filtered_{i*4+3}_greater_{amount}",
                    "nl_query": f"List purchase orders greater than ${amount:,}",
                    "complexity": "filtered",
                    "expected_type": "count",
                    "expected_value": "varies",
                    "validator_type": "count_any"
                },
                {
                    "id": f"filtered_{i*4+4}_less_{amount}",
                    "nl_query": f"Get orders less than ${amount:,}",
                    "complexity": "filtered",
                    "expected_type": "count",
                    "expected_value": "varies",
                    "validator_type": "count_any"
                }
            ])
        
        return queries[:20]  # Return first 20
    
    def _generate_aggregation_queries(self) -> List[Dict[str, Any]]:
        """Generate aggregation queries"""
        queries = []
        
        # Sum aggregations
        queries.extend([
            {
                "id": "agg_1_total_value_all",
                "nl_query": "What is the total value of all orders?",
                "complexity": "aggregation",
                "expected_type": "sum",
                "expected_value": "varies",
                "validator_type": "has_result"
            },
            {
                "id": "agg_2_sum_by_supplier",
                "nl_query": "Calculate total order value by supplier",
                "complexity": "aggregation",
                "expected_type": "group_sum",
                "expected_value": 5,
                "validator_type": "group_count"
            },
            {
                "id": "agg_3_sum_by_department",
                "nl_query": "Sum of orders by department",
                "complexity": "aggregation",
                "expected_type": "group_sum",
                "expected_value": 6,
                "validator_type": "group_count"
            },
            {
                "id": "agg_4_sum_by_status",
                "nl_query": "Total value by order status",
                "complexity": "aggregation",
                "expected_type": "group_sum",
                "expected_value": 3,
                "validator_type": "group_count"
            }
        ])
        
        # Average aggregations
        queries.extend([
            {
                "id": "agg_5_avg_all",
                "nl_query": "What is the average order amount?",
                "complexity": "aggregation",
                "expected_type": "avg",
                "expected_value": "varies",
                "validator_type": "has_result"
            },
            {
                "id": "agg_6_avg_by_supplier",
                "nl_query": "Average order value per supplier",
                "complexity": "aggregation",
                "expected_type": "group_avg",
                "expected_value": 5,
                "validator_type": "group_count"
            },
            {
                "id": "agg_7_avg_by_department",
                "nl_query": "Calculate average order amount by department",
                "complexity": "aggregation",
                "expected_type": "group_avg",
                "expected_value": 6,
                "validator_type": "group_count"
            },
            {
                "id": "agg_8_mean_order_value",
                "nl_query": "What is the mean order value?",
                "complexity": "aggregation",
                "expected_type": "avg",
                "expected_value": "varies",
                "validator_type": "has_result"
            }
        ])
        
        # Min/Max aggregations
        queries.extend([
            {
                "id": "agg_9_max_order",
                "nl_query": "What is the highest order amount?",
                "complexity": "aggregation",
                "expected_type": "max",
                "expected_value": 35000,
                "validator_type": "exact_value"
            },
            {
                "id": "agg_10_min_order",
                "nl_query": "Find the smallest order value",
                "complexity": "aggregation",
                "expected_type": "min",
                "expected_value": 3000,
                "validator_type": "exact_value"
            },
            {
                "id": "agg_11_largest_order",
                "nl_query": "Show me the largest purchase order",
                "complexity": "aggregation",
                "expected_type": "max",
                "expected_value": 35000,
                "validator_type": "exact_value"
            },
            {
                "id": "agg_12_minimum_value",
                "nl_query": "What is the minimum order amount?",
                "complexity": "aggregation",
                "expected_type": "min",
                "expected_value": 3000,
                "validator_type": "exact_value"
            }
        ])
        
        # Count by group
        queries.extend([
            {
                "id": "agg_13_count_by_supplier",
                "nl_query": "Number of orders per supplier",
                "complexity": "aggregation",
                "expected_type": "group_count",
                "expected_value": 5,
                "validator_type": "group_count"
            },
            {
                "id": "agg_14_count_by_dept",
                "nl_query": "Order count by department",
                "complexity": "aggregation",
                "expected_type": "group_count",
                "expected_value": 6,
                "validator_type": "group_count"
            },
            {
                "id": "agg_15_count_by_status",
                "nl_query": "How many orders in each status?",
                "complexity": "aggregation",
                "expected_type": "group_count",
                "expected_value": 3,
                "validator_type": "group_count"
            }
        ])
        
        # Top N queries
        queries.extend([
            {
                "id": "agg_16_top_3_suppliers",
                "nl_query": "Show top 3 suppliers by order count",
                "complexity": "aggregation",
                "expected_type": "top_n",
                "expected_value": 3,
                "validator_type": "exact_count"
            },
            {
                "id": "agg_17_top_5_suppliers",
                "nl_query": "List top 5 suppliers by total value",
                "complexity": "aggregation",
                "expected_type": "top_n",
                "expected_value": 5,
                "validator_type": "exact_count"
            },
            {
                "id": "agg_18_top_departments",
                "nl_query": "Which are the top spending departments?",
                "complexity": "aggregation",
                "expected_type": "group_sum",
                "expected_value": 6,
                "validator_type": "group_count"
            },
            {
                "id": "agg_19_highest_spending_dept",
                "nl_query": "Which department has the highest total spending?",
                "complexity": "aggregation",
                "expected_type": "top_1",
                "expected_value": "IT",
                "validator_type": "top_value"
            },
            {
                "id": "agg_20_most_orders_supplier",
                "nl_query": "Which supplier has the most orders?",
                "complexity": "aggregation",
                "expected_type": "top_1",
                "expected_value": "XYZ Industries",
                "validator_type": "top_value"
            }
        ])
        
        return queries
    
    def _generate_time_based_queries(self) -> List[Dict[str, Any]]:
        """Generate time-based queries"""
        queries = []
        
        # Recent queries
        queries.extend([
            {
                "id": "time_1_last_week",
                "nl_query": "Show orders from last week",
                "complexity": "time_based",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            },
            {
                "id": "time_2_last_month",
                "nl_query": "List orders from the last month",
                "complexity": "time_based",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            },
            {
                "id": "time_3_last_30_days",
                "nl_query": "Get orders from last 30 days",
                "complexity": "time_based",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            },
            {
                "id": "time_4_this_week",
                "nl_query": "Show me orders from this week",
                "complexity": "time_based",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            },
            {
                "id": "time_5_recent_5",
                "nl_query": "What are the 5 most recent orders?",
                "complexity": "time_based",
                "expected_type": "count",
                "expected_value": 5,
                "validator_type": "exact_count"
            }
        ])
        
        # Specific time periods
        queries.extend([
            {
                "id": "time_6_last_7_days",
                "nl_query": "Orders placed in the last 7 days",
                "complexity": "time_based",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            },
            {
                "id": "time_7_last_14_days",
                "nl_query": "Show orders from the past 2 weeks",
                "complexity": "time_based",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            },
            {
                "id": "time_8_last_60_days",
                "nl_query": "List all orders from the last 60 days",
                "complexity": "time_based",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            },
            {
                "id": "time_9_recent_10",
                "nl_query": "Get the 10 most recent purchase orders",
                "complexity": "time_based",
                "expected_type": "count",
                "expected_value": 10,
                "validator_type": "exact_count"
            },
            {
                "id": "time_10_latest_orders",
                "nl_query": "Show me the latest orders",
                "complexity": "time_based",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            }
        ])
        
        # Delivery date queries
        queries.extend([
            {
                "id": "time_11_delivery_this_week",
                "nl_query": "Orders scheduled for delivery this week",
                "complexity": "time_based",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            },
            {
                "id": "time_12_delivery_next_week",
                "nl_query": "What orders are due for delivery next week?",
                "complexity": "time_based",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            },
            {
                "id": "time_13_overdue_deliveries",
                "nl_query": "Show overdue orders",
                "complexity": "time_based",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            },
            {
                "id": "time_14_oldest_orders",
                "nl_query": "What are the oldest pending orders?",
                "complexity": "time_based",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            },
            {
                "id": "time_15_orders_by_month",
                "nl_query": "Group orders by month",
                "complexity": "time_based",
                "expected_type": "group",
                "expected_value": "varies",
                "validator_type": "has_result"
            }
        ])
        
        return queries
    
    def _generate_multi_condition_queries(self) -> List[Dict[str, Any]]:
        """Generate queries with multiple conditions"""
        queries = []
        
        # Two conditions
        queries.extend([
            {
                "id": "multi_1_pending_above_10k",
                "nl_query": "Show pending orders above $10,000",
                "complexity": "multi_condition",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            },
            {
                "id": "multi_2_delivered_it",
                "nl_query": "List delivered orders for IT department",
                "complexity": "multi_condition",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            },
            {
                "id": "multi_3_abc_approved",
                "nl_query": "Show approved orders from ABC Corp",
                "complexity": "multi_condition",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            },
            {
                "id": "multi_4_marketing_above_5k",
                "nl_query": "Marketing orders over $5,000",
                "complexity": "multi_condition",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            },
            {
                "id": "multi_5_xyz_pending",
                "nl_query": "Pending orders from XYZ Industries",
                "complexity": "multi_condition",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            }
        ])
        
        # Three conditions
        queries.extend([
            {
                "id": "multi_6_it_pending_above_10k",
                "nl_query": "Show IT department pending orders above $10,000",
                "complexity": "multi_condition",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            },
            {
                "id": "multi_7_abc_it_delivered",
                "nl_query": "Delivered IT orders from ABC Corp",
                "complexity": "multi_condition",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            },
            {
                "id": "multi_8_tech_marketing_approved",
                "nl_query": "Approved Marketing orders from Tech Solutions Inc",
                "complexity": "multi_condition",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            },
            {
                "id": "multi_9_sales_above_15k_delivered",
                "nl_query": "Delivered Sales orders over $15,000",
                "complexity": "multi_condition",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            },
            {
                "id": "multi_10_xyz_it_above_5k",
                "nl_query": "XYZ Industries IT orders above $5,000",
                "complexity": "multi_condition",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            }
        ])
        
        # Range conditions
        queries.extend([
            {
                "id": "multi_11_between_10k_20k",
                "nl_query": "Orders between $10,000 and $20,000",
                "complexity": "multi_condition",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            },
            {
                "id": "multi_12_between_5k_15k_pending",
                "nl_query": "Pending orders between $5,000 and $15,000",
                "complexity": "multi_condition",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            },
            {
                "id": "multi_13_it_between_10k_25k",
                "nl_query": "IT orders with value between $10,000 and $25,000",
                "complexity": "multi_condition",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            },
            {
                "id": "multi_14_abc_between_5k_20k",
                "nl_query": "ABC Corp orders between $5,000 and $20,000",
                "complexity": "multi_condition",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            },
            {
                "id": "multi_15_delivered_between_10k_30k",
                "nl_query": "Delivered orders with amount between $10,000 and $30,000",
                "complexity": "multi_condition",
                "expected_type": "count",
                "expected_value": "varies",
                "validator_type": "count_any"
            }
        ])
        
        return queries
    
    def _generate_comparison_queries(self) -> List[Dict[str, Any]]:
        """Generate comparison queries"""
        queries = []
        
        queries.extend([
            {
                "id": "comp_1_it_vs_marketing",
                "nl_query": "Compare IT and Marketing department spending",
                "complexity": "comparison",
                "expected_type": "comparison",
                "expected_value": 2,
                "validator_type": "group_count"
            },
            {
                "id": "comp_2_abc_vs_xyz",
                "nl_query": "Compare order counts between ABC Corp and XYZ Industries",
                "complexity": "comparison",
                "expected_type": "comparison",
                "expected_value": 2,
                "validator_type": "group_count"
            },
            {
                "id": "comp_3_pending_vs_delivered",
                "nl_query": "Compare pending vs delivered orders",
                "complexity": "comparison",
                "expected_type": "comparison",
                "expected_value": 2,
                "validator_type": "group_count"
            },
            {
                "id": "comp_4_sales_vs_operations",
                "nl_query": "Which has more orders: Sales or Operations?",
                "complexity": "comparison",
                "expected_type": "comparison",
                "expected_value": 2,
                "validator_type": "group_count"
            },
            {
                "id": "comp_5_tech_vs_global",
                "nl_query": "Compare Tech Solutions Inc vs Global Supplies Ltd total value",
                "complexity": "comparison",
                "expected_type": "comparison",
                "expected_value": 2,
                "validator_type": "group_count"
            },
            {
                "id": "comp_6_hr_vs_finance",
                "nl_query": "HR vs Finance department order comparison",
                "complexity": "comparison",
                "expected_type": "comparison",
                "expected_value": 2,
                "validator_type": "group_count"
            },
            {
                "id": "comp_7_approved_vs_pending",
                "nl_query": "How do approved orders compare to pending?",
                "complexity": "comparison",
                "expected_type": "comparison",
                "expected_value": 2,
                "validator_type": "group_count"
            },
            {
                "id": "comp_8_highest_vs_lowest_dept",
                "nl_query": "Compare highest and lowest spending departments",
                "complexity": "comparison",
                "expected_type": "comparison",
                "expected_value": "varies",
                "validator_type": "has_result"
            },
            {
                "id": "comp_9_most_vs_least_orders",
                "nl_query": "Supplier with most orders vs supplier with least orders",
                "complexity": "comparison",
                "expected_type": "comparison",
                "expected_value": "varies",
                "validator_type": "has_result"
            },
            {
                "id": "comp_10_avg_it_vs_avg_marketing",
                "nl_query": "Compare average order value from departements IT vs Marketing",
                "complexity": "comparison",
                "expected_type": "comparison",
                "expected_value": 2,
                "validator_type": "group_count"
            }
        ])
        
        return queries
    
    def _generate_complex_aggregation_queries(self) -> List[Dict[str, Any]]:
        """Generate complex aggregation queries"""
        queries = []
        
        queries.extend([
            {
                "id": "complex_1_supplier_dept_breakdown",
                "nl_query": "Show order count by supplier and department",
                "complexity": "complex",
                "expected_type": "multi_group",
                "expected_value": "varies",
                "validator_type": "has_result"
            },
            {
                "id": "complex_2_status_dept_value",
                "nl_query": "Total value by status and department",
                "complexity": "complex",
                "expected_type": "multi_group",
                "expected_value": "varies",
                "validator_type": "has_result"
            },
            {
                "id": "complex_3_supplier_status_count",
                "nl_query": "Count orders by supplier and status",
                "complexity": "complex",
                "expected_type": "multi_group",
                "expected_value": "varies",
                "validator_type": "has_result"
            },
            {
                "id": "complex_4_dept_avg_with_count",
                "nl_query": "Average order value by department with order counts",
                "complexity": "complex",
                "expected_type": "multi_agg",
                "expected_value": 6,
                "validator_type": "group_count"
            },
            {
                "id": "complex_5_supplier_sum_avg",
                "nl_query": "Total and average order value per supplier",
                "complexity": "complex",
                "expected_type": "multi_agg",
                "expected_value": 5,
                "validator_type": "group_count"
            },
            {
                "id": "complex_6_top_3_dept_with_details",
                "nl_query": "Top 3 departments by spending with order counts and averages",
                "complexity": "complex",
                "expected_type": "top_n_multi",
                "expected_value": 3,
                "validator_type": "exact_count"
            },
            {
                "id": "complex_7_supplier_metrics",
                "nl_query": "For each supplier show total value, count, and average",
                "complexity": "complex",
                "expected_type": "multi_agg",
                "expected_value": 5,
                "validator_type": "group_count"
            },
            {
                "id": "complex_8_dept_status_matrix",
                "nl_query": "Create a matrix of departments and statuses with counts",
                "complexity": "complex",
                "expected_type": "matrix",
                "expected_value": "varies",
                "validator_type": "has_result"
            },
            {
                "id": "complex_9_percentile_analysis",
                "nl_query": "Show orders in top 25% by value",
                "complexity": "complex",
                "expected_type": "percentile",
                "expected_value": "varies",
                "validator_type": "count_any"
            },
            {
                "id": "complex_10_running_total",
                "nl_query": "Calculate running total of orders by date",
                "complexity": "complex",
                "expected_type": "running_total",
                "expected_value": "varies",
                "validator_type": "has_result"
            }
        ])
        
        return queries
    
    def _generate_edge_case_queries(self) -> List[Dict[str, Any]]:
        """Generate edge case queries"""
        queries = []
        
        queries.extend([
            {
                "id": "edge_1_no_results",
                "nl_query": "Show orders from supplier xyz!",
                "complexity": "edge_case",
                "expected_type": "count",
                "expected_value": 0,
                "validator_type": "exact_count"
            },
            {
                "id": "edge_2_all_statuses",
                "nl_query": "List all possible order statuses",
                "complexity": "edge_case",
                "expected_type": "distinct",
                "expected_value": 3,
                "validator_type": "exact_count"
            },
            {
                "id": "edge_3_all_departments",
                "nl_query": "What departments have placed orders?",
                "complexity": "edge_case",
                "expected_type": "distinct",
                "expected_value": 6,
                "validator_type": "exact_count"
            },
            {
                "id": "edge_4_all_suppliers",
                "nl_query": "List all suppliers in the system",
                "complexity": "edge_case",
                "expected_type": "distinct",
                "expected_value": 5,
                "validator_type": "count_any"
            },
            {
                "id": "edge_5_zero_amount",
                "nl_query": "Are there any orders with zero amount?",
                "complexity": "edge_case",
                "expected_type": "count",
                "expected_value": 0,
                "validator_type": "exact_count"
            }
        ])
        
        return queries


def get_comprehensive_test_queries(complexity_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get comprehensive test queries, optionally filtered by complexity level
    
    Args:
        complexity_filter: Optional filter to get only specific complexity level.
                         Valid values: "simple", "filtered", "aggregation", "time_based",
                         "multi_condition", "comparison", "complex", "edge_case"
                         If None, returns all queries.
    
    Returns:
        List of test query dictionaries
    
    Examples:
        >>> # Get all queries (100+ queries)
        >>> all_queries = get_comprehensive_test_queries()
        >>>
        >>> # Get only simple queries (20 queries)
        >>> simple_queries = get_comprehensive_test_queries(complexity_filter="simple")
        >>>
        >>> # Get only aggregation queries (20 queries)
        >>> agg_queries = get_comprehensive_test_queries(complexity_filter="aggregation")
    """
    generator = ComprehensiveQueryGenerator()
    return generator.generate_all_queries(complexity_filter=complexity_filter)


if __name__ == "__main__":
    import sys
    
    # Check if complexity filter is provided as command line argument
    complexity_filter = sys.argv[1] if len(sys.argv) > 1 else None
    
    if complexity_filter:
        print(f"Generating queries with complexity filter: '{complexity_filter}'")
        print("=" * 80)
    else:
        print("Generating all test queries")
        print("=" * 80)
    
    try:
        # Test the generator with optional filter
        queries = get_comprehensive_test_queries(complexity_filter=complexity_filter)
        print(f"\nGenerated {len(queries)} test queries")
        
        if not complexity_filter:
            print("\nQuery breakdown by complexity:")
            complexity_counts = {}
            for query in queries:
                complexity = query.get("complexity", "unknown")
                complexity_counts[complexity] = complexity_counts.get(complexity, 0) + 1
            
            for complexity, count in sorted(complexity_counts.items()):
                print(f"  {complexity}: {count} queries")
        
        print("\nSample queries:")
        sample_size = min(5, len(queries))
        for i, query in enumerate(queries[:sample_size], 1):
            print(f"\n{i}. {query['nl_query']}")
            print(f"   ID: {query['id']}")
            print(f"   Complexity: {query['complexity']}")
        
        if len(queries) > sample_size:
            print(f"\n... and {len(queries) - sample_size} more queries")
        
        print("\n" + "=" * 80)
        print("Usage examples:")
        print("  python nl_query_generator.py                    # Generate all queries")
        print("  python nl_query_generator.py simple              # Generate only simple queries")
        print("  python nl_query_generator.py aggregation         # Generate only aggregation queries")
        print("  python nl_query_generator.py filtered            # Generate only filtered queries")
        print("\nValid complexity filters:")
        print("  simple, filtered, aggregation, time_based, multi_condition,")
        print("  comparison, complex, edge_case")
        
    except ValueError as e:
        print(f"\nError: {e}")
        print("\nValid complexity filters:")
        print("  simple, filtered, aggregation, time_based, multi_condition,")
        print("  comparison, complex, edge_case")
        sys.exit(1)

# Made with Bob
