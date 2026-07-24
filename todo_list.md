
<!-- table: customers -->
{'customer_id_unique_and_non_null': 'Verify customer_id is not null and unique. Since the column has a row_count of 5025 and a distinct_count of 5000, flag all instances of duplicate IDs and any NULL values.'}: pending
{'first_name_encoding_anomaly': 'Flag rows where first_name contains corrupted text or mojibake, as evidenced by the non-zero encoding_anomaly_count.'}: pending
{'last_name_encoding_anomaly': 'Flag rows where last_name contains corrupted text or mojibake, as evidenced by the non-zero encoding_anomaly_count.'}: pending
{'contact_info_missing': 'Flag any row where both the email column and the phone column are null or blank, as this indicates a customer is unreachable.'}: pending
{'email_format_check': 'Excluding rows already flagged by the contact_info_missing rule, flag any email address that does not contain the '@' symbol.'}: pending
{'phone_placeholder_check': 'Flag rows where the phone value is a lazy default or placeholder string (e.g., 'N/A', '000-000-0000'), as evidenced by the non-zero placeholder_count.'}: pending
{'signup_date_format_check': 'Flag any row where signup_date is not in the format YYYY-MM-DD. Exclude NULLs.'}: pending
{'date_of_birth_future_check': 'Flag any row where date_of_birth is a future date relative to the current date.'}: pending
{'address_placeholder_check': 'Flag rows where address_line1 contains a placeholder value, as evidenced by the non-zero placeholder_count.'}: pending
{'city_whitespace_check': 'Flag rows where city contains leading or trailing whitespace, as evidenced by the non-zero whitespace_count.'}: pending
{'state_casing_normalization': 'Flag any row where the state value differs from the most frequent raw value sharing its trimmed and casefolded form, to correct for inconsistent casing like 'CA' vs 'ca'.'}: pending
{'country_normalization_check': 'Flag any row where the country value differs from the most frequent raw value sharing its trimmed and casefolded form (e.g., 'USA', 'U.S.A.', and 'US' should all align to the most common representative).'}: pending
{'customer_segment_consistency_check': 'Flag any row where the customer_segment value differs from the most frequent raw value sharing its trimmed and casefolded form, addressing casing anomalies.'}: pending
{'postal_code_placeholder_check': 'Flag rows where postal_code contains a placeholder value, as evidenced by the non-zero placeholder_count.'}: pending
{'loyalty_points_negative_check': 'Flag any row where loyalty_points is less than zero.'}: pending

<!-- table: order_items -->
{'pk_not_null_unique': 'Ensure the combination of order_id and line_number is unique and contains no NULL values.'}: pending
{'customer_id_completeness': 'Ensure customer_id is never NULL or empty (blank).'}: pending
{'product_id_no_whitespace': 'Flag rows where product_id contains leading or trailing whitespace.'}: pending
{'sku_no_whitespace': 'Flag rows where sku contains leading or trailing whitespace.'}: pending
{'product_name_no_encoding_anomalies': 'Flag rows where product_name contains encoding anomalies (mojibake).'}: pending
{'unit_price_numeric_positive': 'Flag rows where unit_price is not a valid positive decimal number.'}: pending
{'quantity_numeric_positive': 'Flag rows where quantity is not a valid positive integer (e.g., contains text-based numbers like 'one' or placeholders like 'N/A').'}: pending
{'line_total_consistency': 'Flag rows where the absolute difference between line_total and the calculated value (unit_price * quantity * (1 - (discount_pct / 100.0))) exceeds 0.01. Only evaluate for rows where unit_price and quantity pass numeric validation.'}: pending
{'return_flag_reason_consistency': 'Flag rows where return_flag is TRUE but return_reason is NULL/blank, OR where return_flag is FALSE but return_reason is NOT NULL.'}: pending
{'weight_non_negative': 'Flag rows where weight_kg is negative.'}: pending
{'product_id_name_consistency': 'Flag any row whose product_name differs from the most frequent product_name sharing that product_id.'}: pending
{'product_id_category_consistency': 'Flag any row whose category differs from the most frequent category sharing that product_id.'}: pending

<!-- table: orders -->
{'pk_order_id_unique_non_null': 'Ensure the order_id column contains only unique, non-null values.'}: pending
{'order_date_format_consistent': 'Flag any row where order_date is not in the YYYY-MM-DD ISO-8601 format.'}: pending
{'order_status_canonical_check': 'Flag any row where order_status is not one of the canonical values: 'Delivered', 'Shipped', 'Processing', 'Cancelled', 'Pending', 'Returned'.'}: pending
{'payment_method_placeholder_check': 'Flag any row where payment_method contains placeholders such as 'Unknown', 'unknown', 'N/A', '-', 'xxx', 'NULL', or 'None'.'}: pending
{'item_count_non_negative': 'Flag any row where item_count is less than 1.'}: pending
{'total_amount_math_consistency': 'Flag any row where total_amount (after stripping '$' and casting to numeric) does not equal the sum of subtotal, tax_amount, and shipping_cost. Also flag any row where total_amount is not a valid numeric value.'}: pending
{'ship_date_validity_check': 'Flag any row where status is 'Delivered' or 'Shipped' but ship_date is null. Additionally, flag any row where ship_date is less than order_date.'}: pending
{'shipping_country_casing_consistency': 'Flag any row whose shipping_country differs from the most frequent raw value sharing its trimmed and casefolded form.'}: pending
{'shipping_state_casing_consistency': 'Flag any row whose shipping_state differs from the most frequent raw value sharing its trimmed and casefolded form.'}: pending
{'shipping_postal_code_placeholder_check': 'Flag any row where shipping_postal_code appears to be a placeholder (e.g., non-alphanumeric or clearly lazy-default sequences) given the non-zero placeholder_count.'}: pending
