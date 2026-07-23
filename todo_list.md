
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

<!-- table: customers -->
{'customer_id_unique_non_null': 'The customer_id column must be unique and contain no null values to act as the primary key.'}: pending
{'contact_info_required': 'Every record must have at least one valid method of contact. The combination of email and phone columns must not both be null or empty strings.'}: pending
{'loyalty_points_non_negative': 'The loyalty_points column must contain non-negative values. Rows where loyalty_points is less than 0 are considered invalid.'}: pending
{'signup_date_valid_format': 'The signup_date column is stored as VARCHAR and contains inconsistent date formats. It must be castable to a standard DATE format (e.g., YYYY-MM-DD). Flag rows that do not match a valid date format.'}: pending
{'country_standardization': 'The country column contains redundant variations (e.g., USA, U.S.A., US, United States). Flag rows where country is not the canonical spelling (use the spelling with the highest frequency in the provided value counts).'}: pending
{'city_trim_whitespace': 'The city column must not contain leading or trailing whitespace.'}: pending
{'address_no_unknown_placeholder': 'The address_line1 column should not contain the placeholder value 'Unknown'. Flag all rows where address_line1 is 'Unknown'.'}: pending
{'dob_not_future': 'The date_of_birth column must not contain dates in the future.'}: pending

<!-- table: order_items -->
{'pk_uniqueness_and_not_null': 'The combination of order_id and line_number must not be null and must be unique for every row.'}: pending
{'unit_price_is_positive_numeric': 'The unit_price column must be castable to a numeric value and must be strictly greater than 0.'}: pending
{'quantity_is_positive_integer': 'The quantity column must be castable to an integer and must be strictly greater than 0, excluding any non-numeric placeholders like 'N/A' or text representations.'}: pending
{'discount_pct_range': 'The discount_pct column must be between 0 and 100 inclusive.'}: pending
{'line_total_calculation': 'The line_total column must equal the product of unit_price (casted to double) and quantity (casted to integer), multiplied by (1 - discount_pct/100.0), rounded to 2 decimal places. Exclude rows where unit_price or quantity are non-numeric as these are already captured by their respective format checks.'}: pending
{'return_reason_required': 'If return_flag is true, then return_reason must not be null or empty.'}: pending
{'weight_kg_non_negative': 'The weight_kg column must be greater than or equal to 0.'}: pending
{'tax_rate_non_negative': 'The tax_rate column must be greater than or equal to 0.'}: pending

<!-- table: orders -->
{'check_order_id_unique_not_null': 'The order_id column must be non-null and contain no duplicate values.'}: pending
{'check_order_date_format': 'The order_date column must be in valid YYYY-MM-DD format. Identify rows where the date string does not follow this ISO format (e.g., fails to parse).'}: pending
{'check_ship_date_sequence': 'For rows where ship_date is not null, the ship_date must be greater than or equal to the order_date.'}: pending
{'check_order_status_standardized': 'The order_status column must contain only the following normalized values: 'Delivered', 'Shipped', 'Processing', 'Cancelled', 'Pending', 'Returned'. Flag any rows with variations like 'delivird', 'shiped', 'proccessing', or other misspellings/case-mismatches.'}: pending
{'check_payment_method_validity': 'The payment_method column must not contain placeholders or invalid entries such as 'Unknown', 'None', 'NULL', 'N/A', 'TBD', 'xxx', or '-'.'}: pending
{'check_item_count_positive': 'The item_count column must be greater than 0, as an order cannot contain zero items.'}: pending
{'check_postal_code_length': 'The shipping_postal_code column should not contain suspicious placeholders or fragments; flag rows where the length of the string is less than 3 characters.'}: pending
{'check_financials_non_negative': 'The columns subtotal, tax_amount, and shipping_cost must not be negative.'}: pending
{'check_total_amount_calculation': 'The total_amount (as numeric) must equal the sum of subtotal, tax_amount, and shipping_cost. Only evaluate this check for rows that passed the check_financials_non_negative rule.'}: pending
{'check_currency_country_mapping': 'Ensure consistency between shipping_country and currency (e.g., rows with shipping_country 'USA' should have currency 'USD'). Flag rows where the currency does not match the expected regional standard for that country.'}: pending

<!-- table: customers -->
{'pk_uniqueness': 'Verify that customer_id is unique and not null for all records.'}: pending
{'loyalty_points_non_negative': 'Check that the loyalty_points column contains only non-negative values (greater than or equal to zero).'}: pending
{'email_format_check': 'Validate that the email column follows a standard email format (must contain '@' and '.' characters). Exclude rows where email is NULL.'}: pending
{'signup_date_format_check': 'Verify that the signup_date column (which is stored as VARCHAR) follows a consistent date format (e.g., YYYY-MM-DD). Flag rows that do not match this format, as the samples show inconsistent formatting like '31/07/2022' vs '2023-10-19'.'}: pending
{'country_standardization_check': 'Identify inconsistencies in the country column by flagging variations that represent the same entity, specifically clustering 'USA', 'U.S.A.', 'US', 'United States' and 'UK', 'U.K.', 'United Kingdom'.'}: pending
{'contact_info_presence': 'Ensure that every customer record has at least one valid contact method by checking that either email or phone is not null and not empty.'}: pending
{'signup_after_birth_date': 'Check that the signup_date is chronologically after the date_of_birth. Apply only to rows where both signup_date and date_of_birth contain valid, non-null date values.'}: pending
{'update_after_signup_date': 'Check that the last_updated date is greater than or equal to the signup_date. Apply only to rows where both fields contain valid, non-null date values.'}: pending
{'phone_format_sanity': 'Flag rows in the phone column containing non-numeric conversational text (e.g., 'call-ME'). Exclude rows where phone is NULL.'}: pending

<!-- table: customers -->
{'customer_id_unique_not_null': 'Verify that the customer_id column contains no NULL values and that every value is unique, confirming its role as the primary key.'}: pending
{'country_standardization': 'Identify rows where the country value is an inconsistent alias, such as 'USA', 'U.S.A.', 'US', and 'United States' or 'UK', 'U.K.', and 'United Kingdom', suggesting multiple spelling variations for the same country.'}: pending
{'signup_date_format_check': 'Verify that all values in the signup_date column strictly follow the YYYY-MM-DD date format. Flag any rows where the date is formatted differently, such as MM/DD/YYYY, or contains non-date strings.'}: pending
{'last_updated_logic': 'Verify that the last_updated date is greater than or equal to the signup_date. Exclude rows where signup_date is NULL or failed the signup_date_format_check rule.'}: pending
{'future_date_of_birth': 'Verify that date_of_birth is not a date in the future relative to the current date.'}: pending
{'loyalty_points_non_negative': 'Verify that the loyalty_points column contains no negative values.'}: pending
{'missing_contact_info': 'Verify that each customer has at least one form of contact; flag rows where both email and phone columns are NULL.'}: pending
{'state_format_trim': 'Verify that the state column does not contain leading or trailing whitespace characters, identifying inconsistent data entry like ' MA '.'}: pending

<!-- table: order_items -->
{'pk_uniqueness': 'The combination of order_id and line_number must be unique and not null.'}: pending
{'line_number_positive': 'The column line_number must be greater than 0.'}: pending
{'quantity_valid_positive_integer': 'The column quantity must contain only valid positive integers. It currently contains non-numeric strings (like N/A, two, several) and negative values which must be excluded.'}: pending
{'unit_price_valid_positive_numeric': 'The column unit_price must contain only valid positive numeric values. It is currently stored as VARCHAR and must be castable to a positive float.'}: pending
{'discount_pct_range': 'The column discount_pct must be between 0 and 100 inclusive.'}: pending
{'line_total_calculation': 'The column line_total should equal (CAST(unit_price AS DOUBLE) * CAST(quantity AS DOUBLE) * (1 - discount_pct / 100.0)). Exclude rows where unit_price or quantity values are invalid as these are already caught by the unit_price_valid_positive_numeric and quantity_valid_positive_integer rules.'}: pending
{'return_reason_required': 'If return_flag is TRUE, return_reason must not be NULL.'}: pending
{'sku_whitespace_check': 'The column sku should not have leading or trailing whitespace.'}: pending
{'weight_kg_positive': 'The column weight_kg must be greater than 0.'}: pending
{'tax_rate_non_negative': 'The column tax_rate must be greater than or equal to 0.'}: pending

<!-- table: orders -->
{'pk_check': 'Verify that order_id is unique and does not contain null values.'}: pending
{'customer_id_required': 'Verify that customer_id is not null for every order.'}: pending
{'order_date_format': 'Verify that order_date matches the YYYY-MM-DD format. Any value not following this date pattern is invalid.'}: pending
{'order_status_normalization': 'Verify that order_status is one of the following standardized values: 'Delivered', 'Shipped', 'Processing', 'Cancelled', 'Pending', 'Returned'. All variations (case differences, typos like 'delivird') should be flagged as invalid.'}: pending
{'payment_method_validity': 'Verify that payment_method contains a valid payment type. Rows with values such as 'Unknown', 'N/A', 'NULL', '-', or 'xxx' must be flagged as invalid.'}: pending
{'item_count_positive': 'Verify that item_count is greater than 0.'}: pending
{'tax_amount_non_negative': 'Verify that tax_amount is greater than or equal to 0.'}: pending
{'total_amount_format': 'Verify that total_amount string can be cast to a numeric value. It should not contain non-numeric characters other than a leading '$' symbol or grouping commas.'}: pending
{'total_amount_math': 'Verify that the numeric value of total_amount equals the sum of subtotal, tax_amount, and shipping_cost. Exclude rows that failed the total_amount_format check.'}: pending
{'ship_date_sequence': 'Verify that ship_date is greater than or equal to order_date for all rows where ship_date is not null.'}: pending

<!-- table: customers -->
{'pk_uniqueness': 'Ensure customer_id is not null and unique across the table.'}: pending
{'contact_info_present': 'Verify that every row has either a non-blank, non-null email or a non-blank, non-null phone number.'}: pending
{'email_format': 'Ensure email values contain an '@' symbol and a valid domain format. Exclude rows where the email is blank as caught by the contact_info_present rule.'}: pending
{'loyalty_points_non_negative': 'Verify that loyalty_points are greater than or equal to zero.'}: pending
{'date_of_birth_past': 'Ensure date_of_birth is in the past (<= current date).'}: pending
{'signup_date_format': 'Verify that signup_date strictly follows the YYYY-MM-DD format, flagging inconsistent formats like 'Month DD, YYYY'.'}: pending
{'dates_logical_consistency': 'Ensure last_updated is greater than or equal to signup_date.'}: pending
{'first_name_encoding': 'Flag rows where first_name contains encoding anomalies.'}: pending
{'last_name_encoding': 'Flag rows where last_name contains encoding anomalies.'}: pending
{'phone_placeholder': 'Flag rows where phone contains common placeholder strings (e.g., 'n/a', '000-000-0000').'}: pending
{'address_placeholder': 'Flag rows where address_line1 contains placeholder strings.'}: pending
{'postal_code_placeholder': 'Flag rows where postal_code contains placeholder strings.'}: pending
{'country_standardization': 'Flag rows where country is not one of the standardized values (e.g., 'USA', 'India', 'UK', etc.) to address the high casing and spelling variation counts.'}: pending
{'city_whitespace': 'Flag city values containing leading or trailing whitespace.'}: pending
{'state_casing': 'Flag state values with casing inconsistencies.'}: pending
{'customer_segment_casing': 'Flag customer_segment values that do not match the expected casing (e.g., 'Standard', 'VIP').'}: pending

<!-- table: customers -->
{'customer_id_unique': 'The customer_id column must be unique and non-null for all records.'}: pending
{'email_completeness': 'The email column must not be NULL or contain only blank/whitespace characters.'}: pending
{'email_format': 'The email column must contain a valid format, including an '@' symbol and a valid domain suffix. Exclude rows already caught by the email_completeness rule.'}: pending
{'phone_completeness': 'The phone column must not be NULL or contain only blank/whitespace characters.'}: pending
{'phone_validity': 'The phone column must not contain placeholders (e.g., 'N/A') or casing anomalies. Exclude rows already caught by the phone_completeness rule.'}: pending
{'signup_date_format': 'The signup_date column must be in YYYY-MM-DD format. Exclude NULL values.'}: pending
{'address_line1_placeholder': 'The address_line1 column must not contain common placeholder strings.'}: pending
{'city_cleanliness': 'The city column must not contain leading or trailing whitespace and must be consistently cased.'}: pending
{'state_cleanliness': 'The state column must not contain leading or trailing whitespace and must be consistently cased.'}: pending
{'country_standardization': 'The country column must be normalized to a standardized set of country names (e.g., 'USA' instead of 'US' or 'U.S.A.').'}: pending
{'customer_segment_casing': 'The customer_segment column must be consistently cased.'}: pending
{'loyalty_points_non_negative': 'The loyalty_points column must be greater than or equal to zero.'}: pending
{'first_name_encoding': 'The first_name column must be free of encoding anomalies.'}: pending
{'last_name_encoding': 'The last_name column must be free of encoding anomalies.'}: pending
{'postal_code_placeholder': 'The postal_code column must not contain common placeholder strings.'}: pending

<!-- table: order_items -->
{'pk_order_items_uniqueness': 'Ensure the combination of order_id and line_number is unique and does not contain any null values across the entire table.'}: pending
{'order_id_pattern_check': 'Verify that order_id follows the format 'ORD' followed by exactly 7 digits.'}: pending
{'customer_id_pattern_check': 'Verify that customer_id follows the format 'CUST' followed by exactly 6 digits.'}: pending
{'product_sku_whitespace_check': 'Flag rows in product_id and sku columns that contain leading or trailing whitespace.'}: pending
{'product_name_encoding_check': 'Flag rows in the product_name column that contain garbled characters or encoding anomalies.'}: pending
{'unit_price_validity': 'Ensure unit_price is a valid numeric string that is greater than 0.'}: pending
{'quantity_validity': 'Ensure quantity is a valid numeric string representing a positive integer. This check implicitly captures rows with text placeholders, negative numbers, or non-numeric values like 'several'.'}: pending
{'line_total_accuracy': 'Verify that the line_total column equals the calculated result of (unit_price * quantity * (1 - discount_pct / 100.0) * (1 + tax_rate)). Skip rows already flagged by the unit_price_validity or quantity_validity rules.'}: pending
{'discount_pct_range': 'Ensure discount_pct is between 0 and 100 inclusive.'}: pending
{'tax_rate_non_negative': 'Ensure tax_rate is greater than or equal to 0.'}: pending
{'return_dependency_check': 'If return_flag is FALSE, return_reason must be NULL or blank. If return_flag is TRUE, return_reason must not be NULL or blank.'}: pending
{'category_validity': 'Ensure the category column only contains the 10 known valid categories (Toys & Games, Office Supplies, Apparel, Grocery, Electronics, Books, Home & Kitchen, Sports & Outdoors, Automotive, Beauty & Personal Care).'}: pending
{'warehouse_code_validity': 'Ensure the warehouse_code column only contains one of the four known valid codes: WH-EAST, WH-CENTRAL, WH-INTL, or WH-WEST.'}: pending
{'uom_validity': 'Ensure the unit_of_measure column is either 'each' or 'pack'.'}: pending
{'weight_positive': 'Ensure the weight_kg column contains only non-negative values.'}: pending

<!-- table: orders -->
{'order_id_completeness_and_uniqueness': 'The order_id column must contain no null values and must be fully unique across the entire table, serving as the primary key.'}: pending
{'customer_id_format_check': 'The customer_id column must not be null and must match the pattern 'CUST' followed by digits.'}: pending
{'order_date_format_check': 'The order_date column must follow a valid date format (e.g., YYYY-MM-DD, DD/MM/YYYY, or MM/DD/YYYY) that can be successfully parsed into a date type.'}: pending
{'ship_date_consistency': 'For all rows where ship_date is not null, the ship_date value must be greater than or equal to the parsed value of the order_date column.'}: pending
{'order_status_standardization': 'The order_status column must contain only canonical, case-insensitive values: 'Delivered', 'Shipped', 'Processing', 'Cancelled', 'Pending', or 'Returned'.'}: pending
{'payment_method_validity': 'The payment_method column must not contain placeholders such as 'Unknown', 'N/A', 'NULL', '-', or 'xxx'.'}: pending
{'item_count_positive': 'The item_count column must contain values greater than 0.'}: pending
{'shipping_postal_code_validity': 'The shipping_postal_code column must not contain placeholders as indicated by the placeholder_count check.'}: pending
{'shipping_country_validity': 'The shipping_country column must be one of the following canonical values: 'USA', 'United Kingdom', 'India', 'Canada', 'Australia', 'Germany', or 'France'.'}: pending
{'total_amount_calculation_accuracy': 'The total_amount column must be a valid numeric string, and its value must equal the sum of subtotal, tax_amount, and shipping_cost. Exclude rows where total_amount is not a valid number.'}: pending
