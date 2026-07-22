
<!-- table: customers -->
{'pk_customer_id_validation': 'The customer_id column must be non-null and unique for all records to function as the primary key.'}: pending
{'email_format_and_completeness': 'The email column must contain a valid email format (containing '@' and a domain) and must not be null.'}: pending
{'phone_format_sanity': 'The phone column must contain numeric characters. Exclude rows where phone is null; flag any rows where values are descriptive text (e.g., 'call me maybe') rather than standard phone formatting.'}: pending
{'country_standardization': 'The country column contains inconsistent labels for the same entities (e.g., 'USA', 'US', 'U.S.A.'). Standardize all country values to a single canonical list and flag non-matching values.'}: pending
{'date_of_birth_logic': 'The date_of_birth column must be a date in the past relative to the current date; future dates are invalid.'}: pending
{'signup_date_format_check': 'The signup_date column is stored as VARCHAR and must contain a valid date format. Flag rows where the string cannot be cast to a date.'}: pending
{'date_consistency_check': 'The signup_date must not be later than the last_updated date. Exclude rows caught by the signup_date_format_check rule or rows where either date is null to avoid double counting.'}: pending
{'loyalty_points_non_negative': 'The loyalty_points column must be greater than or equal to zero; negative values indicate an error.'}: pending

<!-- table: customers -->
{'check_pk_customer_id': 'Ensure customer_id is not null and is unique across all rows in the customers table.'}: pending
{'check_email_placeholders': 'Flag rows where the email column contains invalid placeholder strings such as 'N/A' or 'None'.'}: pending
{'check_email_format': 'Verify that non-null email addresses match a valid pattern (e.g., contains '@' and a domain structure). Exclude rows already caught by check_email_placeholders.'}: pending
{'check_country_standardization': 'Ensure the country column contains standardized country names (e.g., 'United States', 'United Kingdom', 'Canada', 'India', 'Australia', 'Germany', 'France') rather than abbreviations like 'US', 'IN', 'CA' or variations like 'U.S.A.' or 'United States of America'.'}: pending
{'check_dob_not_future': 'Verify that date_of_birth is not a date in the future relative to the current date.'}: pending
{'check_signup_date_format': 'Verify that the signup_date column (stored as VARCHAR) conforms to a valid 'YYYY-MM-DD' date format.'}: pending
{'check_signup_date_not_future': 'Ensure that the signup_date is not a date in the future. Exclude rows that failed the check_signup_date_format rule.'}: pending
{'check_signup_date_after_dob': 'Ensure that the signup_date is chronologically later than the date_of_birth. Exclude rows that failed either the check_signup_date_format or check_dob_not_future rules.'}: pending
{'check_loyalty_points_non_negative': 'Verify that the loyalty_points column contains no negative values.'}: pending
{'check_phone_placeholder': 'Flag rows where the phone column contains the value 'Unknown'.'}: pending

<!-- table: customers -->
{'pk_customer_id_unique_not_null': 'The customer_id column is the primary key and must contain only unique, non-null values. The current distinct_count (3000) against row_count (3022) indicates this rule is currently being violated.'}: pending
{'country_value_standardization': 'The country column contains inconsistent variants for the same country (e.g., 'USA', 'US', 'U.S.A.', 'United States'). Flag rows where the value is not one of the standardized, high-frequency names ('USA', 'United Kingdom', 'India', 'Canada', 'Australia', 'Germany', 'France').'}: pending
{'loyalty_points_non_negative': 'The loyalty_points column should only contain positive integers or zero. Flag any rows containing negative values.'}: pending
{'customer_date_logical_consistency': 'The signup_date (cast to date) must not be after the last_updated date, and the date_of_birth must be strictly earlier than the signup_date. Exclude rows from this check if signup_date is not in a valid date format.'}: pending
{'contact_information_missing': 'Every customer record must have at least one way to be reached. Flag rows where both the email column and the phone column are null.'}: pending
{'email_format_validation': 'The email column, where not null, must follow a standard email format containing an '@' symbol and a domain extension. Exclude rows already flagged by the contact_information_missing rule.'}: pending

<!-- table: order_items -->
{'pk_composite_integrity': 'The combination of order_id and line_number must be non-null and unique to ensure each line item is identified correctly.'}: pending
{'quantity_format_validation': 'The quantity column must contain only positive integer values. Flag any rows containing non-numeric strings (e.g., 'one dozen', 'several', 'two') or negative numbers (e.g., '-1', '-2').'}: pending
{'unit_price_format_validation': 'The unit_price column must be a valid, positive numeric value. Flag any rows where the value cannot be parsed as a positive number.'}: pending
{'discount_pct_range': 'The discount_pct column must be a valid percentage between 0 and 100 inclusive.'}: pending
{'line_total_math_accuracy': 'The line_total must be equal to the result of (CAST(quantity AS FLOAT) * CAST(unit_price AS FLOAT) * (1 - (discount_pct / 100.0))). Exclude any rows already flagged by quantity_format_validation to avoid double-counting.'}: pending
{'currency_consistency': 'The currency column must always be 'USD'.'}: pending
{'added_date_future_check': 'The added_date column should not contain dates that are in the future relative to the current date.'}: pending

<!-- table: orders -->
{'order_id_unique_and_not_null': 'Ensure that the order_id column is unique and contains no null values.'}: pending
{'order_date_format_check': 'Ensure that order_date strictly follows the YYYY-MM-DD date format.'}: pending
{'ship_date_logic': 'Verify that ship_date is greater than or equal to order_date for all records where ship_date is not null.'}: pending
{'order_status_standardization': 'Verify that order_status values, after trimming whitespace and ignoring case, belong to the accepted set: 'Delivered', 'Shipped', 'Pending', 'Cancelled', 'Processing', 'Returned', 'Complete', 'Refunded', 'Back Order', 'In Transit'.'}: pending
{'payment_method_validity': 'Flag rows where payment_method contains invalid placeholders including 'N/A', 'Unknown', 'TBD', or '-'.'}: pending
{'total_amount_format_check': 'Verify that total_amount is a valid numeric string capable of being cast to a double.'}: pending
{'pricing_integrity_check': 'Verify that the sum of subtotal, tax_amount, and shipping_cost equals total_amount. Exclude rows where total_amount is not a valid numeric format (already caught by total_amount_format_check).'}: pending
{'item_count_positive_check': 'Verify that item_count is greater than 0 for every record.'}: pending
