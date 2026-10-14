"""DAX definitions, formats, display folders and business descriptions."""
M=[]
def add(name,expression,fmt='0',folder='01 Core',description=''):
    M.append(dict(name=name,expression=expression,formatString=fmt,displayFolder=folder,description=description or name))
def scoped(expression):
    return f'''VAR MatchingOrders = VALUES(fact_order_items[order_id])
VAR ProductOrSellerFilter = ISCROSSFILTERED(dim_product) || ISCROSSFILTERED(dim_seller)
RETURN IF(ProductOrSellerFilter,
    CALCULATE({expression}, KEEPFILTERS(TREATAS(MatchingOrders, fact_orders[order_id]))),
    {expression})'''
money='"R$" #,0.00;("R$" #,0.00);"R$" 0.00'
add('Total Revenue','SUM(fact_order_items[revenue])',money,description='Gross item value plus freight, all statuses unless filtered. Not net recognized revenue; no refund data.')
add('Orders',scoped('COUNTROWS(fact_orders)'),'#,0',description='Distinct order-grain rows; category/seller uses virtual order membership without double counting.')
add('AOV','DIVIDE([Total Revenue], [Orders])',money,description='Selected item revenue divided by matching orders. Category selection gives selected-category spend per matching order.')
add('Delivered Orders','CALCULATE([Orders], KEEPFILTERS(fact_orders[order_status] = "delivered"))','#,0')
add('Delivery Eligible Orders','CALCULATE([Delivered Orders], KEEPFILTERS(NOT ISBLANK(fact_orders[delay_days])))','#,0','02 Delivery')
add('Late Orders','CALCULATE([Delivery Eligible Orders], KEEPFILTERS(fact_orders[is_late] = TRUE()))','#,0','02 Delivery')
add('Late Delivery %','DIVIDE([Late Orders], [Delivery Eligible Orders])','0.00%','02 Delivery','Delivered orders with positive calendar-day delay / delivered orders with both dates.')
add('Delay Sum',scoped('SUM(fact_orders[delay_days])'),'#,0','02 Delivery')
add('Avg Delay Days','DIVIDE(CALCULATE([Delay Sum], KEEPFILTERS(fact_orders[order_status]="delivered"), KEEPFILTERS(fact_orders[is_late]=TRUE())), [Late Orders])','0.0','02 Delivery','Mean delay among late delivered orders only.')
add('Review Points',scoped('SUM(fact_orders[review_score])'),'#,0','03 Reviews')
add('Reviewed Orders',scoped('COUNT(fact_orders[review_score])'),'#,0','03 Reviews')
add('Delivered Reviewed Orders','CALCULATE([Reviewed Orders], KEEPFILTERS(fact_orders[order_status]="delivered"))','#,0','03 Reviews')
add('Avg Review Score','DIVIDE(CALCULATE([Review Points], KEEPFILTERS(fact_orders[order_status]="delivered")), [Delivered Reviewed Orders])','0.00','03 Reviews','Latest valid review per delivered order. Missing reviews are excluded, never scored as zero.')
add('Low Review Orders','CALCULATE([Delivered Reviewed Orders], KEEPFILTERS(fact_orders[review_score] IN {1,2}))','#,0','03 Reviews')
add('Low Review %','DIVIDE([Low Review Orders], [Delivered Reviewed Orders])','0.00%','03 Reviews')
add('Late Reviewed Orders','CALCULATE([Delivered Reviewed Orders], KEEPFILTERS(fact_orders[is_late]=TRUE()), KEEPFILTERS(NOT ISBLANK(fact_orders[delay_days])))','#,0','03 Reviews')
add('On-time Reviewed Orders','CALCULATE([Delivered Reviewed Orders], KEEPFILTERS(fact_orders[is_late]==FALSE()), KEEPFILTERS(NOT ISBLANK(fact_orders[delay_days])))','#,0','03 Reviews')
for label,test in [('Late','TRUE()'),('On-time','FALSE()')]:
    add(f'Low Review % ({label})',f'DIVIDE(CALCULATE([Low Review Orders], KEEPFILTERS(fact_orders[is_late]=={test}), KEEPFILTERS(NOT ISBLANK(fact_orders[delay_days]))), [{label} Reviewed Orders])','0.00%','03 Reviews')
    add(f'Avg Rating ({label})',f'CALCULATE([Avg Review Score], KEEPFILTERS(fact_orders[is_late]=={test}), KEEPFILTERS(NOT ISBLANK(fact_orders[delay_days])))','0.00','03 Reviews')
add('Late vs On-time Gap (pp)','VAR LateRate = [Low Review % (Late)]\nVAR OnTimeRate = [Low Review % (On-time)]\nRETURN IF(NOT ISBLANK(LateRate) && NOT ISBLANK(OnTimeRate), (LateRate-OnTimeRate)*100)','0.00 "pp"','03 Reviews')
add('Revenue MoM %','VAR PriorMonth = CALCULATE([Total Revenue], DATEADD(dim_date[Date], -1, MONTH))\nRETURN DIVIDE([Total Revenue]-PriorMonth, PriorMonth)','0.0%','04 Time','Uses purchase date. Edge months are partial; percent change is blank when prior revenue is zero/missing.')
add('Revenue YTD','TOTALYTD([Total Revenue], dim_date[Date])',money,'04 Time')
add('Revenue Same Period Last Year','CALCULATE([Total Revenue], SAMEPERIODLASTYEAR(dim_date[Date]))',money,'04 Time')
add('Delivered Customers','COUNTROWS(FILTER(VALUES(dim_customer[customer_unique_id]), CALCULATE([Delivered Orders]) > 0))','#,0','05 Customers')
add('Repeat Customers','COUNTROWS(FILTER(VALUES(dim_customer[customer_unique_id]), CALCULATE([Delivered Orders]) >= 2))','#,0','05 Customers')
add('Repeat Customer %','DIVIDE([Repeat Customers], [Delivered Customers])','0.00%','05 Customers','Customers with at least two delivered orders in current filter context / customers with at least one. Not cohort-adjusted retention.')
add('Customers by RFM Segment','[Delivered Customers]','#,0','05 Customers','Delivered customers in current filters, grouped by static RFM snapshot segment.')
add('Revenue Share of Top 10 Categories','''VAR CategoryRevenue = ADDCOLUMNS(ALLSELECTED(dim_product[category]), "@Revenue", CALCULATE([Total Revenue]))
VAR TopCategories = TOPN(10, CategoryRevenue, [@Revenue], DESC, dim_product[category], ASC)
RETURN DIVIDE(SUMX(TopCategories, [@Revenue]), SUMX(CategoryRevenue, [@Revenue]))''','0.0%','01 Core')
add('Top 10 Category Revenue','''VAR RankedCategories = ADDCOLUMNS(ALLSELECTED(dim_product[category]), "@Revenue", CALCULATE([Total Revenue]))
VAR TopCategories = TOPN(10, RankedCategories, [@Revenue], DESC, dim_product[category], ASC)
RETURN CALCULATE([Total Revenue], KEEPFILTERS(TopCategories))''',money,'01 Core')
add('Late Reduction % Value','SELECTEDVALUE(\'Late Reduction %\'[Value], 0.50)','0%','06 Scenario','Disconnected what-if table, 0 to 100% in 5-point increments, default 50%.')
add('Late Orders Avoided','VAR Reduction = [Late Reduction % Value]\nRETURN [Late Orders] * Reduction','#,0','06 Scenario')
add('Low Reviews Avoided','''VAR Gap = [Low Review % (Late)] - [Low Review % (On-time)]
RETURN IF([Late Reviewed Orders]>0 && [On-time Reviewed Orders]>0, [Late Orders Avoided] * Gap)''','#,0','06 Scenario','Requested scenario extrapolates reviewed cohort rates to all late orders. Expected count, not a guaranteed outcome.')
add('Projected Avg Rating','''VAR ReviewedLateShifted = [Late Reviewed Orders] * [Late Reduction % Value]
VAR RatingUplift = [Avg Rating (On-time)] - [Avg Rating (Late)]
VAR Baseline = [Avg Review Score]
RETURN IF([Late Reviewed Orders]>0 && [On-time Reviewed Orders]>0,
    MIN(5, MAX(1, Baseline + DIVIDE(ReviewedLateShifted * RatingUplift, [Delivered Reviewed Orders]))))''','0.00','06 Scenario','Reassigns selected share of reviewed late orders to observed on-time mean; keeps review volume fixed. Associational scenario.')
add('Scenario Rating','SWITCH(SELECTEDVALUE(Scenario[Scenario]), "Before", [Avg Review Score], "After", [Projected Avg Rating])','0.00','06 Scenario')
add('Scenario Late Orders','SWITCH(SELECTEDVALUE(Scenario[Scenario]), "Before", [Late Orders], "After", [Late Orders]-[Late Orders Avoided])','#,0','06 Scenario')
add('Delivery Insight','''VAR LateRate = [Low Review % (Late)]
VAR OnTimeRate = [Low Review % (On-time)]
RETURN IF(ISBLANK(LateRate) || ISBLANK(OnTimeRate), "Insufficient reviewed orders for a cohort comparison",
"Late deliveries receive 1–2 star reviews " & FORMAT(LateRate,"0.0%") & " of the time vs " & FORMAT(OnTimeRate,"0.0%") & " on-time")''','General','07 Narrative')
add('Executive Insight','"Top 10 categories generate " & FORMAT([Revenue Share of Top 10 Categories],"0.0%") & " of gross sales. Prioritize delivery reliability in these categories."','General','07 Narrative')
add('Scenario Insight','"Illustrative scenario: " & FORMAT([Late Reduction % Value],"0%") & " fewer late orders. Observed cohort differences are associations, not causal effects."','General','07 Narrative')
add('Retention Insight','"Only " & FORMAT([Repeat Customer %],"0.0%") & " of delivered customers purchased again within the selected observation window."','General','07 Narrative')
