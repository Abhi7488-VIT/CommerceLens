"""Power Query sources. Cleaning rules C01-C16 run once in export_star_schema.py; each table query only reads its CSV."""

SCHEMA = {
 'fact_orders': [('order_id','string'),('customer_unique_id','string'),('state','string'),('order_status','string'),('purchase_date','dateTime'),('delivered_date','dateTime'),('estimated_date','dateTime'),('item_revenue','decimal'),('item_count','int64'),('payment_total','decimal'),('payment_count','int64'),('delivery_days','int64'),('estimated_days','int64'),('delay_days','int64'),('is_late','boolean'),('review_score','int64'),('is_low_review','boolean'),('delivery_group','string'),('delay_bin','int64')],
 'fact_order_items':[('order_id','string'),('order_item_id','int64'),('product_id','string'),('seller_id','string'),('price','decimal'),('freight_value','decimal'),('revenue','decimal')],
 'dim_customer':[('customer_unique_id','string'),('city','string'),('state','string'),('recency','int64'),('frequency','int64'),('monetary','decimal'),('rfm_segment','string')],
 'dim_product':[('product_id','string'),('category','string')],
 'dim_seller':[('seller_id','string'),('seller_city','string'),('seller_state','string')],
 'dim_state':[('state','string'),('latitude','double'),('longitude','double'),('country','string')],
 'dim_date':[('Date','dateTime'),('year','int64'),('quarter','string'),('month','int64'),('month_name','string'),('week','int64'),('year_month','string')],
 'cleaning_log':[('step','string'),('detail','string'),('affected_rows','int64')]
}

M_TYPES = {'string': 'type text', 'int64': 'Int64.Type', 'decimal': 'Currency.Type', 'double': 'type number', 'boolean': 'type logical', 'dateTime': 'type date'}

def partition(name):
    """Read one star-schema CSV from DataFolder, promote headers, set types. No merges, groups or query references."""
    types = ', '.join('{"%s", %s}' % (c, M_TYPES[t]) for c, t in SCHEMA[name])
    return ('let\n'
            '    Source = Csv.Document(File.Contents(Text.TrimEnd(DataFolder, "\\") & "\\' + name + '.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),\n'
            '    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),\n'
            '    Typed = Table.TransformColumnTypes(Promoted, {' + types + '}, "en-US")\n'
            'in\n    Typed')
