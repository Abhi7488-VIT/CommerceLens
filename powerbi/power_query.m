// CommerceLens Power Query. Each table reads one CSV written by export_star_schema.py; no merges or query references.
section CommerceLens;

shared DataFolder = "C:\CommerceLens\powerbi\data" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true];

// fact_orders; enable load for this query.
shared #"fact_orders" = let
    Source = Csv.Document(File.Contents(Text.TrimEnd(DataFolder, "\") & "\fact_orders.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"order_id", type text}, {"customer_unique_id", type text}, {"state", type text}, {"order_status", type text}, {"purchase_date", type date}, {"delivered_date", type date}, {"estimated_date", type date}, {"item_revenue", Currency.Type}, {"item_count", Int64.Type}, {"payment_total", Currency.Type}, {"payment_count", Int64.Type}, {"delivery_days", Int64.Type}, {"estimated_days", Int64.Type}, {"delay_days", Int64.Type}, {"is_late", type logical}, {"review_score", Int64.Type}, {"is_low_review", type logical}, {"delivery_group", type text}, {"delay_bin", Int64.Type}}, "en-US")
in
    Typed;

// fact_order_items; enable load for this query.
shared #"fact_order_items" = let
    Source = Csv.Document(File.Contents(Text.TrimEnd(DataFolder, "\") & "\fact_order_items.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"order_id", type text}, {"order_item_id", Int64.Type}, {"product_id", type text}, {"seller_id", type text}, {"price", Currency.Type}, {"freight_value", Currency.Type}, {"revenue", Currency.Type}}, "en-US")
in
    Typed;

// dim_customer; enable load for this query.
shared #"dim_customer" = let
    Source = Csv.Document(File.Contents(Text.TrimEnd(DataFolder, "\") & "\dim_customer.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"customer_unique_id", type text}, {"city", type text}, {"state", type text}, {"recency", Int64.Type}, {"frequency", Int64.Type}, {"monetary", Currency.Type}, {"rfm_segment", type text}}, "en-US")
in
    Typed;

// dim_product; enable load for this query.
shared #"dim_product" = let
    Source = Csv.Document(File.Contents(Text.TrimEnd(DataFolder, "\") & "\dim_product.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"product_id", type text}, {"category", type text}}, "en-US")
in
    Typed;

// dim_seller; enable load for this query.
shared #"dim_seller" = let
    Source = Csv.Document(File.Contents(Text.TrimEnd(DataFolder, "\") & "\dim_seller.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"seller_id", type text}, {"seller_city", type text}, {"seller_state", type text}}, "en-US")
in
    Typed;

// dim_state; enable load for this query.
shared #"dim_state" = let
    Source = Csv.Document(File.Contents(Text.TrimEnd(DataFolder, "\") & "\dim_state.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"state", type text}, {"latitude", type number}, {"longitude", type number}, {"country", type text}}, "en-US")
in
    Typed;

// dim_date; enable load for this query.
shared #"dim_date" = let
    Source = Csv.Document(File.Contents(Text.TrimEnd(DataFolder, "\") & "\dim_date.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"Date", type date}, {"year", Int64.Type}, {"quarter", type text}, {"month", Int64.Type}, {"month_name", type text}, {"week", Int64.Type}, {"year_month", type text}}, "en-US")
in
    Typed;

// cleaning_log; enable load for this query.
shared #"cleaning_log" = let
    Source = Csv.Document(File.Contents(Text.TrimEnd(DataFolder, "\") & "\cleaning_log.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"step", type text}, {"detail", type text}, {"affected_rows", Int64.Type}}, "en-US")
in
    Typed;

// Late Reduction %; enable load for this query.
shared #"Late Reduction %" = Table.FromColumns({List.Transform({0..20}, each _ / 20)}, type table [Value=number]);

// Scenario; enable load for this query.
shared #"Scenario" = #table(type table [Scenario=text, Sort=Int64.Type], {{"Before",1},{"After",2}});

