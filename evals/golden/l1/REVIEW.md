# Level-1 golden set v1 · review sheet

For each case: is the expected result what the tool *should* return for this catalogue?
Mark `ok`, or write what is wrong. Prices in EUR; ✗ = out of stock.

## l1-001 · `get_categories` `{}`
*11 categories with listing counts, in-stock counts, price range and subcategories*

- **beauty-wellness** 17/18 in stock, €36 to 399 · Bath 2/2, Fitness 2/2, Fragrance 2/2, Grooming 3/3, Recovery 3/4, Skincare 3/3, Sleep 2/2
- **books-stationery** 15/16 in stock, €6.5 to 129 · Books 4/4, Craft 2/2, Paper 6/7, Pens 3/3
- **experiences** 2/2 in stock, €50 to 100 · Gift Cards 2/2
- **games-puzzles** 11/12 in stock, €26 to 145 · Board Games 5/5, Classic Games 3/3, Puzzles 3/4
- **home-living** 26/28 in stock, €28 to 249 · Candles 2/3, Decor 5/5, Fragrance 3/3, Garden 3/3, Lighting 2/2, Storage 3/3, Textiles 5/6, Vases 3/3
- **jewellery** 7/8 in stock, €54 to 195 · Bracelets 0/1, Earrings 2/2, Necklaces 2/2, Rings 2/2, Watches 1/1
- **kids** 6/6 in stock, €34 to 96 · Books 1/1, Craft 1/1, Toys 4/4
- **kitchen-dining** 22/24 in stock, €42 to 189 · Bar 3/3, Coffee 3/4, Cookware 4/4, Knives 3/3, Serving 4/4, Tableware 3/4, Tea 2/2
- **outdoor-travel** 9/10 in stock, €32 to 189 · Bags 3/3, Drinkware 4/4, Outdoor 2/3
- **pets** 2/3 in stock, €28 to 149 · Cats 0/1, Dogs 2/2
- **tech-gadgets** 24/25 in stock, €22 to 899 · Audio 6/6, Creative 1/2, Desk 5/5, Home Tech 5/5, Mobile 2/2, Photo 2/2, Reading 2/2, Wearable 1/1

Review: 

## l1-002 · `get_products_by_category` `{"category": "kitchen-dining"}`
*default page: in stock only, best rated first, 5 items*

- **product_ids**:
  - `KD-001` Chef's Knife 20cm · €149 · ★4.8 (394) · anyone · ships 3d
  - `KD-013` Enamel Casserole 24cm · €189 · ★4.8 (312) · anyone · ships 5d
  - `KD-006` Burr Coffee Grinder, Manual · €115 · ★4.7 (241) · anyone · ships 3d
  - `KD-020` Salt & Pepper Mills, Pair · €92 · ★4.7 (176) · anyone · ships 4d
  - `KD-009` Crystal Whisky Glasses, Pair · €89 · ★4.7 (132) · him · ships 4d
- **total_matches**: `22`

Review: 

## l1-003 · `get_products_by_category` `{"category": "Kitchen and Dining"}`
*category name in another spelling resolves to the slug*

- **product_ids**:
  - `KD-001` Chef's Knife 20cm · €149 · ★4.8 (394) · anyone · ships 3d
  - `KD-013` Enamel Casserole 24cm · €189 · ★4.8 (312) · anyone · ships 5d
  - `KD-006` Burr Coffee Grinder, Manual · €115 · ★4.7 (241) · anyone · ships 3d
  - `KD-020` Salt & Pepper Mills, Pair · €92 · ★4.7 (176) · anyone · ships 4d
  - `KD-009` Crystal Whisky Glasses, Pair · €89 · ★4.7 (132) · him · ships 4d
- **total_matches**: `22`

Review: 

## l1-004 · `get_products_by_category` `{"category": "kitchen"}`
*one distinctive word resolves to its category*

- **product_ids**:
  - `KD-001` Chef's Knife 20cm · €149 · ★4.8 (394) · anyone · ships 3d
  - `KD-013` Enamel Casserole 24cm · €189 · ★4.8 (312) · anyone · ships 5d
  - `KD-006` Burr Coffee Grinder, Manual · €115 · ★4.7 (241) · anyone · ships 3d
  - `KD-020` Salt & Pepper Mills, Pair · €92 · ★4.7 (176) · anyone · ships 4d
  - `KD-009` Crystal Whisky Glasses, Pair · €89 · ★4.7 (132) · him · ships 4d
- **total_matches**: `22`

Review: 

## l1-005 · `get_products_by_category` `{"category": "garden"}`
*unknown category is a recoverable error, not an empty list*

- **error_code**: `"unknown_category"`

Review: 

## l1-006 · `get_products_by_category` `{"category": "home-living", "subcategory": "candles"}`
*subcategory filter, case-insensitive; out-of-stock candle reported*

- **product_ids**:
  - `HL-003` Ember Ceramic Candle · €42 · ★4.8 (431) · anyone · ships 2d
  - `HL-005` Trio Votive Set · €54 · ★4.5 (97) · anyone · ships 2d
- **total_matches**: `2`
- **out_of_stock_matches**:
  - ✗ `HL-004` Linen Fig Candle · €38 · ★4.7 (289) · her · ships 2d

Review: 

## l1-007 · `get_products_by_category` `{"category": "home-living", "subcategory": "Lamps"}`
*unknown subcategory is a recoverable error*

- **error_code**: `"unknown_subcategory"`

Review: 

## l1-008 · `get_products_by_category` `{"category": "pets", "subcategory": "cats"}`
*the only cat product is out of stock: empty page, reported, not hidden*

- **product_ids**: *(none)*
- **total_matches**: `0`
- **out_of_stock_matches**:
  - ✗ `PT-003` Cat Tree, Compact · €119 · ★4.0 (96) · anyone · ships 6d

Review: 

## l1-009 · `get_products_by_category` `{"category": "pets", "subcategory": "cats", "include_out_of_stock": true}`
*include_out_of_stock returns it*

- **product_ids**:
  - ✗ `PT-003` Cat Tree, Compact · €119 · ★4.0 (96) · anyone · ships 6d
- **total_matches**: `1`

Review: 

## l1-010 · `get_products_by_category` `{"category": "experiences"}`
*Experiences holds only the two gift cards*

- **product_ids**:
  - `EX-001` Gift Card, 50 EUR · €50 · no reviews (0) · anyone · ships 0d
  - `EX-002` Gift Card, 100 EUR · €100 · no reviews (0) · anyone · ships 0d
- **total_matches**: `2`

Review: 

## l1-011 · `get_products_by_category` `{"category": "kitchen-dining", "max_price": 40}`
*max_price is inclusive*

- **product_ids**: *(none)*
- **total_matches**: `0`
- **suggestions**: `[{"change": "max_price", "to": 42.0, "would_match": 1}]`

Review: 

## l1-012 · `get_products_by_category` `{"category": "kitchen-dining", "min_price": 50, "max_price": 70}`
*price range*

- **product_ids**:
  - `KD-002` Paring Knife 9cm · €69 · ★4.6 (148) · anyone · ships 3d
  - `KD-003` Knife Sharpening Stone · €54 · ★4.5 (96) · him · ships 3d
  - `KD-023` Amber Glass Tumbler Set · €56 · ★4.5 (86) · anyone · ships 4d
  - `KD-021` Tea Infuser Pot · €68 · ★4.3 (102) · her · ships 3d
  - `KD-012` Slate Cheese Board Set · €62 · ★4.2 (87) · anyone · ships 3d
- **total_matches**: `6`

Review: 

## l1-013 · `get_products_by_category` `{"category": "jewellery", "recipient": "her"}`
*recipient includes products for anyone*

- **product_ids**:
  - `JW-001` Gold Vermeil Chain Necklace · €165 · ★4.6 (289) · her · ships 4d
  - `JW-003` Huggie Earrings, Pair · €89 · ★4.5 (217) · her · ships 3d
  - `JW-002` Pearl Pendant · €128 · ★4.4 (134) · her · ships 4d
  - `JW-004` Stud Set, Three Pairs · €112 · ★4.3 (96) · her · ships 3d
  - `JW-006` Stacking Rings, Set of Three · €96 · ★4.2 (143) · her · ships 4d
- **total_matches**: `5`

Review: 

## l1-014 · `get_products_by_category` `{"category": "home-living", "occasion": "housewarming", "max_price": 50}`
*occasion plus price*

- **product_ids**:
  - `HL-023` Terrazzo Coaster Set · €32 · ★4.4 (111) · anyone · ships 3d
  - `HL-018` Entry Tray, Walnut · €44 · ★4.4 (63) · him · ships 3d
  - `HL-007` Stoneware Vase, Squat · €49 · ★4.3 (51) · anyone · ships 4d
  - `HL-012` Reed Diffuser, Cedar · €46 · ★4.1 (118) · anyone · ships 2d
  - `HL-028` Linen Table Runner · €48 · ★4.0 (41) · her · ships 3d
- **total_matches**: `7`

Review: 

## l1-015 · `get_products_by_category` `{"category": "tech-gadgets", "max_shipping_days": 2}`
*deadline filter*

- **product_ids**:
  - `TG-006` E-Reader 7in Glare-Free · €199 · ★4.8 (923) · anyone · ships 2d
  - `TG-001` Wireless Headphones ANC · €279 · ★4.7 (842) · anyone · ships 2d
  - `TG-002` Wireless Earbuds Pro · €189 · ★4.5 (1204) · anyone · ships 2d
  - `TG-004` Portable Speaker, Waterproof · €99 · ★4.4 (676) · anyone · ships 2d
  - `TG-016` Laptop Stand, Folding · €64 · ★4.4 (214) · anyone · ships 2d
- **total_matches**: `14`

Review: 

## l1-016 · `get_products_by_category` `{"category": "beauty-wellness", "exclude": "scent,fragrance,candle"}`
*exclusions by word*

- **product_ids**:
  - `BW-001` Silk Pillowcase Pair · €119 · ★4.7 (486) · her · ships 3d
  - `BW-004` Vitamin C Serum 30ml · €64 · ★4.6 (721) · her · ships 2d
  - `BW-007` Safety Razor Set · €89 · ★4.6 (231) · him · ships 3d
  - `BW-017` Yoga Mat, Cork · €98 · ★4.6 (187) · her · ships 4d
  - `BW-002` Weighted Eye Mask · €42 · ★4.5 (312) · her · ships 2d
- **total_matches**: `14`

Review: 

## l1-017 · `get_products_by_category` `{"category": "kids", "max_price": 30}`
*nothing under 30 in Kids: empty page and the filter to drop*

- **product_ids**: *(none)*
- **total_matches**: `0`
- **suggestions**: `[{"change": "max_price", "to": 34.0, "would_match": 1}]`

Review: 

## l1-018 · `get_products_by_category` `{"category": "jewellery", "recipient": "her", "occasion": "anniversary", "max_price": 100}`
*strict filters return few: suggestion names the filter to drop*

- **product_ids**: *(none)*
- **total_matches**: `0`
- **suggestions**: `[{"change": "occasion", "to": null, "would_match": 2}, {"change": "max_price", "to": 128.0, "would_match": 1}]`

Review: 

## l1-019 · `get_products_by_category` `{"category": "tech-gadgets", "sort": "price_asc"}`
*cheapest first*

- **product_ids**:
  - `TG-020` Film Twin Pack · €22 · ★4.1 (203) · anyone · ships 2d
  - `TG-013` Switch Sampler Pack · €24 · ★4.3 (127) · him · ships 2d
  - `TG-007` E-Reader Case, Fabric · €39 · ★4.2 (241) · anyone · ships 2d
  - `TG-018` Magnetic Wallet Stand · €45 · ★3.8 (164) · him · ships 2d
  - `TG-009` Smart Plug, Pack of Four · €54 · ★4.1 (527) · anyone · ships 2d
- **total_matches**: `24`

Review: 

## l1-020 · `get_products_by_category` `{"category": "tech-gadgets", "sort": "price_desc"}`
*most expensive first*

- **product_ids**:
  - `TG-025` Bookshelf Speakers, Pair · €899 · ★4.9 (76) · him · ships 7d
  - `TG-005` Turntable, Belt Drive · €349 · ★4.6 (198) · him · ships 5d
  - `TG-024` Smart Ring, Sleep Tracking · €329 · ★3.9 (142) · anyone · ships 4d
  - `TG-001` Wireless Headphones ANC · €279 · ★4.7 (842) · anyone · ships 2d
  - `TG-006` E-Reader 7in Glare-Free · €199 · ★4.8 (923) · anyone · ships 2d
- **total_matches**: `24`

Review: 

## l1-021 · `get_products_by_category` `{"category": "books-stationery", "sort": "popularity"}`
*popularity is review count*

- **product_ids**:
  - `BS-004` Hardcover Notebook A5, Dotted · €28 · ★4.6 (512) · anyone · ships 2d
  - `BS-010` Atlas of Remote Islands · €36 · ★4.8 (341) · anyone · ships 3d
  - `BS-001` Fountain Pen, Medium Nib · €129 · ★4.7 (264) · anyone · ships 3d
  - `BS-005` Notebook Trio A6 · €24 · ★4.3 (203) · anyone · ships 2d
  - `BS-009` The Art of Slow Cooking · €42 · ★4.6 (178) · anyone · ships 3d
- **total_matches**: `15`

Review: 

## l1-022 · `get_products_by_category` `{"category": "home-living", "limit": 5, "offset": 5}`
*second page*

- **product_ids**:
  - `HL-015` Marble Bookends · €95 · ★4.6 (58) · him · ships 5d
  - `HL-014` Nordic Wall Clock · €89 · ★4.5 (132) · anyone · ships 4d
  - `HL-005` Trio Votive Set · €54 · ★4.5 (97) · anyone · ships 2d
  - `HL-024` Amber Glass Tumbler Set · €56 · ★4.5 (86) · anyone · ships 4d
  - `HL-010` Waffle Cotton Throw · €78 · ★4.4 (203) · anyone · ships 3d
- **total_matches**: `26`

Review: 

## l1-023 · `get_products_by_category` `{"category": "home-living", "limit": 25}`
*limit above 10 is clamped to 10*

- **product_ids**:
  - `HL-009` Alpaca Throw · €185 · ★4.9 (156) · anyone · ships 5d
  - `HL-003` Ember Ceramic Candle · €42 · ★4.8 (431) · anyone · ships 2d
  - `HL-027` Incense Set, Japanese · €28 · ★4.7 (224) · anyone · ships 2d
  - `HL-001` Aurora Table Lamp · €129 · ★4.6 (212) · anyone · ships 3d
  - `HL-025` Sheepskin Rug, Small · €120 · ★4.6 (72) · anyone · ships 5d
  - `HL-015` Marble Bookends · €95 · ★4.6 (58) · him · ships 5d
  - `HL-014` Nordic Wall Clock · €89 · ★4.5 (132) · anyone · ships 4d
  - `HL-005` Trio Votive Set · €54 · ★4.5 (97) · anyone · ships 2d
  - `HL-024` Amber Glass Tumbler Set · €56 · ★4.5 (86) · anyone · ships 4d
  - `HL-010` Waffle Cotton Throw · €78 · ★4.4 (203) · anyone · ships 3d
- **total_matches**: `26`

Review: 

## l1-024 · `get_products_by_category` `{"category": "home-living", "limit": 10, "offset": 10}`
*third page of ten; cross-listed HL-021 appears in Home & Living under its HL id*

- **product_ids**:
  - `HL-023` Terrazzo Coaster Set · €32 · ★4.4 (111) · anyone · ships 3d
  - `HL-002` Halden Floor Lamp · €249 · ★4.4 (88) · anyone · ships 4d
  - `HL-018` Entry Tray, Walnut · €44 · ★4.4 (63) · him · ships 3d
  - `HL-017` Woven Storage Basket · €58 · ★4.3 (77) · anyone · ships 4d
  - `HL-006` Stoneware Vase, Tall · €68 · ★4.3 (64) · anyone · ships 4d
  - `HL-007` Stoneware Vase, Squat · €49 · ★4.3 (51) · anyone · ships 4d
  - `HL-019` Ceramic Planter, Medium · €52 · ★4.2 (94) · anyone · ships 4d
  - `HL-011` Linen Cushion Pair · €64 · ★4.2 (71) · anyone · ships 3d
  - `HL-021` Herb Garden Kit · €42 · ★4.1 (167) · anyone · ships 3d
  - `HL-012` Reed Diffuser, Cedar · €46 · ★4.1 (118) · anyone · ships 2d
- **total_matches**: `26`

Review: 

## l1-025 · `get_products_by_category` `{"category": "kitchen-dining", "sort": "price_asc", "limit": 10}`
*cross-listed products appear in Kitchen & Dining under their KD ids*

- **product_ids**:
  - `KD-024` Herb Garden Kit · €42 · ★4.1 (167) · anyone · ships 3d
  - `KD-022` Loose Leaf Tea Flight · €44 · ★4.2 (138) · anyone · ships 2d
  - `KD-004` Espresso Moka Pot 3-cup · €46 · ★4.4 (276) · anyone · ships 2d
  - `KD-003` Knife Sharpening Stone · €54 · ★4.5 (96) · him · ships 3d
  - `KD-023` Amber Glass Tumbler Set · €56 · ★4.5 (86) · anyone · ships 4d
  - `KD-012` Slate Cheese Board Set · €62 · ★4.2 (87) · anyone · ships 3d
  - `KD-010` Wine Preserver · €64 · ★3.9 (68) · anyone · ships 3d
  - `KD-021` Tea Infuser Pot · €68 · ★4.3 (102) · her · ships 3d
  - `KD-002` Paring Knife 9cm · €69 · ★4.6 (148) · anyone · ships 3d
  - `KD-016` Bread Baking Set · €72 · ★4.4 (121) · anyone · ships 4d
- **total_matches**: `22`

Review: 

## l1-026 · `search_products` `{"query": "chef knife", "max_price": 100}`
*specific request with no exact answer: the €149 chef's knife is reported over budget*

- **product_ids**:
  - `KD-002` Paring Knife 9cm · €69 · ★4.6 (148) · anyone · ships 3d
  - `KD-003` Knife Sharpening Stone · €54 · ★4.5 (96) · him · ships 3d
  - `KD-012` Slate Cheese Board Set · €62 · ★4.2 (87) · anyone · ships 3d
- **total_matches**: `3`
- **over_budget_matches**:
  - `KD-001` Chef's Knife 20cm · €149 · ★4.8 (394) · anyone · ships 3d
- **suggestions**: `[{"change": "max_price", "to": 149.0, "would_match": 4}]`

Review: 

## l1-027 · `search_products` `{"query": "chef knife"}`
*the same request without a budget finds the chef's knife first*

- **product_ids**:
  - `KD-001` Chef's Knife 20cm · €149 · ★4.8 (394) · anyone · ships 3d
  - `KD-002` Paring Knife 9cm · €69 · ★4.6 (148) · anyone · ships 3d
  - `KD-003` Knife Sharpening Stone · €54 · ★4.5 (96) · him · ships 3d
  - `KD-012` Slate Cheese Board Set · €62 · ★4.2 (87) · anyone · ships 3d
- **total_matches**: `4`

Review: 

## l1-028 · `search_products` `{"query": "city map jigsaw"}`
*a product asked for by name that is out of stock is reported, not hidden*

- **product_ids**:
  - `GP-006` Jigsaw 1000pc, Botanical · €32 · ★4.4 (276) · her · ships 2d
  - `BS-010` Atlas of Remote Islands · €36 · ★4.8 (341) · anyone · ships 3d
- **total_matches**: `2`
- **out_of_stock_matches**:
  - ✗ `GP-007` Jigsaw 1000pc, City Map · €32 · ★4.2 (194) · him · ships 2d

Review: 

## l1-029 · `search_products` `{"query": "fig candle"}`
*out-of-stock fig candle reported; the in-stock trio with a fig scent is returned*

- **product_ids**:
  - `HL-003` Ember Ceramic Candle · €42 · ★4.8 (431) · anyone · ships 2d
  - `BW-009` Eau de Parfum, Fig & Cedar · €145 · ★4.5 (203) · anyone · ships 3d
  - `HL-005` Trio Votive Set · €54 · ★4.5 (97) · anyone · ships 2d
- **total_matches**: `3`
- **out_of_stock_matches**:
  - ✗ `HL-004` Linen Fig Candle · €38 · ★4.7 (289) · her · ships 2d

Review: 

## l1-030 · `search_products` `{"query": "housewarming", "max_price": 50}`
*an occasion word in the query matches tags and text*

- **product_ids**:
  - `BS-009` The Art of Slow Cooking · €42 · ★4.6 (178) · anyone · ships 3d
  - `KD-004` Espresso Moka Pot 3-cup · €46 · ★4.4 (276) · anyone · ships 2d
  - `HL-023` Terrazzo Coaster Set · €32 · ★4.4 (111) · anyone · ships 3d
  - `HL-018` Entry Tray, Walnut · €44 · ★4.4 (63) · him · ships 3d
  - `HL-007` Stoneware Vase, Squat · €49 · ★4.3 (51) · anyone · ships 4d
- **total_matches**: `11`
- **over_budget_matches**:
  - `HL-019` Ceramic Planter, Medium · €52 · ★4.2 (94) · anyone · ships 4d
  - `TG-009` Smart Plug, Pack of Four · €54 · ★4.1 (527) · anyone · ships 2d

Review: 

## l1-031 · `search_products` `{"query": "sony noise cancelling headphones"}`
*a brand the shop does not sell is reported as unmatched*

- **product_ids**:
  - `TG-001` Wireless Headphones ANC · €279 · ★4.7 (842) · anyone · ships 2d
  - `TG-023` Noise Machine · €58 · ★4.2 (268) · anyone · ships 2d
- **total_matches**: `2`
- **unmatched_terms**: `["sony"]`

Review: 

## l1-032 · `search_products` `{"query": "iphone"}`
*nothing matches: empty, unmatched term, no invention*

- **product_ids**: *(none)*
- **total_matches**: `0`
- **unmatched_terms**: `["iphone"]`

Review: 

## l1-033 · `search_products` `{"query": "cuchillo"}`
*a non-English word matches nothing: the agent must translate*

- **product_ids**: *(none)*
- **total_matches**: `0`
- **unmatched_terms**: `["cuchillo"]`

Review: 

## l1-034 · `search_products` `{"query": "asdfghjkl"}`
*nonsense matches nothing*

- **product_ids**: *(none)*
- **total_matches**: `0`
- **unmatched_terms**: `["asdfghjkl"]`

Review: 

## l1-035 · `search_products` `{"query": "herb garden kit"}`
*cross-listed product appears once, under its primary id*

- **product_ids**:
  - `HL-021` Herb Garden Kit · €42 · ★4.1 (167) · anyone · ships 3d
  - `KD-008` Cocktail Kit, Ten-Piece · €129 · ★4.5 (158) · him · ships 4d
  - `KD-015` Pasta Making Kit · €98 · ★4.3 (93) · anyone · ships 4d
  - `BW-006` Beard Care Kit · €68 · ★4.2 (176) · him · ships 3d
  - `KI-004` Junior Science Kit · €62 · ★4.2 (158) · kids · ships 3d
- **total_matches**: `12`

Review: 

## l1-036 · `search_products` `{"query": "amber glass tumbler"}`
*the second cross-listed product appears once, under its primary id*

- **product_ids**:
  - `HL-024` Amber Glass Tumbler Set · €56 · ★4.5 (86) · anyone · ships 4d
  - `KD-009` Crystal Whisky Glasses, Pair · €89 · ★4.7 (132) · him · ships 4d
  - `BW-004` Vitamin C Serum 30ml · €64 · ★4.6 (721) · her · ships 2d
  - `BW-006` Beard Care Kit · €68 · ★4.2 (176) · him · ships 3d
  - `HL-012` Reed Diffuser, Cedar · €46 · ★4.1 (118) · anyone · ships 2d
- **total_matches**: `21`
- **out_of_stock_matches**:
  - ✗ `KD-007` Cold Brew Carafe · €52 · ★4.1 (74) · anyone · ships 3d

Review: 

## l1-037 · `search_products` `{"query": "coffee", "max_price": 60}`
*keyword plus budget across categories*

- **product_ids**:
  - `KD-004` Espresso Moka Pot 3-cup · €46 · ★4.4 (276) · anyone · ships 2d
  - `OT-002` Travel Mug, Leakproof · €38 · ★4.4 (512) · anyone · ships 2d
- **total_matches**: `2`
- **out_of_stock_matches**:
  - ✗ `KD-007` Cold Brew Carafe · €52 · ★4.1 (74) · anyone · ships 3d
- **over_budget_matches**:
  - `KD-006` Burr Coffee Grinder, Manual · €115 · ★4.7 (241) · anyone · ships 3d
  - `KD-005` Pour-Over Set · €78 · ★4.6 (183) · him · ships 3d
- **suggestions**: `[{"change": "max_price", "to": 78.0, "would_match": 3}]`

Review: 

## l1-038 · `search_products` `{"query": "throw blanket", "exclude": "alpaca,wool,sheepskin"}`
*vegan-style exclusions on materials*

- **product_ids**:
  - `HL-010` Waffle Cotton Throw · €78 · ★4.4 (203) · anyone · ships 3d
  - `BW-016` Sauna Blanket · €399 · ★3.7 (58) · anyone · ships 7d
  - `HL-001` Aurora Table Lamp · €129 · ★4.6 (212) · anyone · ships 3d
  - `HL-017` Woven Storage Basket · €58 · ★4.3 (77) · anyone · ships 4d
  - `HL-026` Oak Serving Ladder · €110 · no reviews (0) · anyone · ships 6d
- **total_matches**: `5`

Review: 

## l1-039 · `search_products` `{"query": "puzzle", "sort": "price_asc"}`
*explicit sort overrides relevance*

- **product_ids**:
  - `GP-003` Two-Player Card Game · €26 · ★4.6 (417) · couple · ships 2d
  - `GP-006` Jigsaw 1000pc, Botanical · €32 · ★4.4 (276) · her · ships 2d
  - `GP-004` Party Game, Eighty Prompts · €34 · ★3.9 (229) · anyone · ships 2d
  - `GP-008` Metal Puzzle Set, Six · €38 · ★4.0 (151) · anyone · ships 2d
  - `GP-012` Escape Room in a Box · €44 · ★4.1 (208) · couple · ships 2d
- **total_matches**: `11`
- **out_of_stock_matches**:
  - ✗ `GP-007` Jigsaw 1000pc, City Map · €32 · ★4.2 (194) · him · ships 2d

Review: 

## l1-040 · `search_products` `{"query": "running"}`
*a hobby word that lives in tags*

- **product_ids**:
  - `TG-003` Open-Ear Sport Buds · €129 · ★4.1 (317) · him · ships 2d
- **total_matches**: `1`

Review: 

## l1-041 · `search_products` `{"query": "pasta"}`
*pasta matches the pasta kit (the agent decides if the shopper meant money)*

- **product_ids**:
  - `KD-018` Handmade Pasta Bowls, Pair · €74 · ★4.6 (58) · couple · ships 4d
  - `KD-015` Pasta Making Kit · €98 · ★4.3 (93) · anyone · ships 4d
- **total_matches**: `2`

Review: 

## l1-042 · `search_products` `{"query": "candle", "include_out_of_stock": true}`
*include_out_of_stock mixes them into the ranking*

- **product_ids**:
  - `HL-003` Ember Ceramic Candle · €42 · ★4.8 (431) · anyone · ships 2d
  - ✗ `HL-004` Linen Fig Candle · €38 · ★4.7 (289) · her · ships 2d
  - `HL-005` Trio Votive Set · €54 · ★4.5 (97) · anyone · ships 2d
- **total_matches**: `3`

Review: 

## l1-043 · `search_products` `{"query": "travel", "recipient": "him", "max_shipping_days": 3}`
*recipient plus deadline*

- **product_ids**:
  - `OT-002` Travel Mug, Leakproof · €38 · ★4.4 (512) · anyone · ships 2d
  - `BS-010` Atlas of Remote Islands · €36 · ★4.8 (341) · anyone · ships 3d
  - `TG-001` Wireless Headphones ANC · €279 · ★4.7 (842) · anyone · ships 2d
  - `OT-005` Packing Cube Set · €52 · ★4.5 (368) · anyone · ships 2d
  - `TG-017` Power Bank 20000mAh · €69 · ★4.3 (738) · anyone · ships 2d
- **total_matches**: `10`
- **out_of_stock_matches**:
  - ✗ `OT-008` Camping Hammock · €68 · ★4.5 (221) · him · ships 3d

Review: 

## l1-044 · `search_products` `{"query": "headphones", "max_price": 150}`
*every ANC option costs more than 150: over-budget matches*

- **product_ids**: *(none)*
- **total_matches**: `0`
- **over_budget_matches**:
  - `TG-001` Wireless Headphones ANC · €279 · ★4.7 (842) · anyone · ships 2d
- **suggestions**: `[{"change": "max_price", "to": 279.0, "would_match": 1}]`

Review: 

## l1-045 · `search_products` `{"query": "anniversary", "recipient": "her", "max_price": 100}`
*an occasion word in the query matches the occasion tags; better matches over budget are reported*

- **product_ids**:
  - `HL-024` Amber Glass Tumbler Set · €56 · ★4.5 (86) · anyone · ships 4d
  - `KD-015` Pasta Making Kit · €98 · ★4.3 (93) · anyone · ships 4d
  - `HL-006` Stoneware Vase, Tall · €68 · ★4.3 (64) · anyone · ships 4d
  - `HL-016` Brass Picture Frame 13x18 · €39 · ★4.0 (89) · anyone · ships 3d
  - `EX-001` Gift Card, 50 EUR · €50 · no reviews (0) · anyone · ships 0d
- **total_matches**: `6`
- **over_budget_matches**:
  - `HL-026` Oak Serving Ladder · €110 · no reviews (0) · anyone · ships 6d
  - `BW-001` Silk Pillowcase Pair · €119 · ★4.7 (486) · her · ships 3d

Review: 

## l1-046 · `search_products` `{}`
*no query: best rated in the whole catalogue*

- **product_ids**:
  - `HL-009` Alpaca Throw · €185 · ★4.9 (156) · anyone · ships 5d
  - `TG-025` Bookshelf Speakers, Pair · €899 · ★4.9 (76) · him · ships 7d
  - `TG-006` E-Reader 7in Glare-Free · €199 · ★4.8 (923) · anyone · ships 2d
  - `HL-003` Ember Ceramic Candle · €42 · ★4.8 (431) · anyone · ships 2d
  - `KD-001` Chef's Knife 20cm · €149 · ★4.8 (394) · anyone · ships 3d
- **total_matches**: `139`

Review: 

## l1-047 · `search_products` `{"sort": "price_asc"}`
*no query: the cheapest products in the catalogue*

- **product_ids**:
  - `BS-015` Letterpress Card, Single · €6.5 · ★3.6 (31) · anyone · ships 2d
  - `BS-012` Poetry Anthology, Pocket · €22 · ★4.3 (89) · her · ships 2d
  - `TG-020` Film Twin Pack · €22 · ★4.1 (203) · anyone · ships 2d
  - `BS-005` Notebook Trio A6 · €24 · ★4.3 (203) · anyone · ships 2d
  - `TG-013` Switch Sampler Pack · €24 · ★4.3 (127) · him · ships 2d
- **total_matches**: `139`

Review: 

## l1-048 · `search_products` `{"sort": "popularity", "limit": 3}`
*no query: the most reviewed*

- **product_ids**:
  - `TG-002` Wireless Earbuds Pro · €189 · ★4.5 (1204) · anyone · ships 2d
  - `TG-006` E-Reader 7in Glare-Free · €199 · ★4.8 (923) · anyone · ships 2d
  - `TG-001` Wireless Headphones ANC · €279 · ★4.7 (842) · anyone · ships 2d
- **total_matches**: `139`

Review: 

## l1-049 · `search_products` `{"recipient": "kids", "max_price": 40}`
*no query, filters only*

- **product_ids**:
  - `BS-010` Atlas of Remote Islands · €36 · ★4.8 (341) · anyone · ships 3d
  - `HL-027` Incense Set, Japanese · €28 · ★4.7 (224) · anyone · ships 2d
  - `BS-004` Hardcover Notebook A5, Dotted · €28 · ★4.6 (512) · anyone · ships 2d
  - `KI-003` Illustrated Story Collection · €34 · ★4.6 (213) · kids · ships 2d
  - `OT-002` Travel Mug, Leakproof · €38 · ★4.4 (512) · anyone · ships 2d
- **total_matches**: `18`

Review: 

## l1-050 · `search_products` `{"max_shipping_days": 0}`
*same-day: only digital gift cards*

- **product_ids**:
  - `EX-001` Gift Card, 50 EUR · €50 · no reviews (0) · anyone · ships 0d
  - `EX-002` Gift Card, 100 EUR · €100 · no reviews (0) · anyone · ships 0d
- **total_matches**: `2`
- **suggestions**: `[{"change": "max_shipping_days", "to": null, "would_match": 139}]`

Review: 

## l1-051 · `search_products` `{"max_price": 10}`
*almost nothing under 10*

- **product_ids**:
  - `BS-015` Letterpress Card, Single · €6.5 · ★3.6 (31) · anyone · ships 2d
- **total_matches**: `1`
- **suggestions**: `[{"change": "max_price", "to": 22.0, "would_match": 3}]`

Review: 

## l1-052 · `search_products` `{"min_price": 300}`
*only the most expensive items*

- **product_ids**:
  - `TG-025` Bookshelf Speakers, Pair · €899 · ★4.9 (76) · him · ships 7d
  - `TG-005` Turntable, Belt Drive · €349 · ★4.6 (198) · him · ships 5d
  - `TG-024` Smart Ring, Sleep Tracking · €329 · ★3.9 (142) · anyone · ships 4d
  - `BW-016` Sauna Blanket · €399 · ★3.7 (58) · anyone · ships 7d
- **total_matches**: `4`
- **suggestions**: `[{"change": "min_price", "to": 279.0, "would_match": 5}]`

Review: 

## l1-053 · `get_product_details` `{"product_id": "KD-001"}`
*an in-stock product: no alternatives block*

- **product_id**: `"KD-001"`

Review: 

## l1-054 · `get_product_details` `{"product_id": "HL-004"}`
*out of stock: in-stock alternatives from the same subcategory first*

- **product_id**: `"HL-004"`
- **in_stock_alternatives**:
  - `HL-003` Ember Ceramic Candle · €42 · ★4.8 (431) · anyone · ships 2d
  - `HL-005` Trio Votive Set · €54 · ★4.5 (97) · anyone · ships 2d
  - `HL-016` Brass Picture Frame 13x18 · €39 · ★4.0 (89) · anyone · ships 3d

Review: 

## l1-055 · `get_product_details` `{"product_id": "PT-003"}`
*out of stock with no sibling in its subcategory: alternatives from its category*

- **product_id**: `"PT-003"`
- **in_stock_alternatives**:
  - `PT-001` Dog Bed, Orthopaedic · €149 · ★4.5 (178) · anyone · ships 5d
  - `PT-002` Rope Toy Bundle · €28 · ★4.1 (264) · anyone · ships 2d

Review: 

## l1-056 · `get_product_details` `{"product_id": "KD-007"}`
*out-of-stock coffee product: alternatives closest in price*

- **product_id**: `"KD-007"`
- **in_stock_alternatives**:
  - `KD-004` Espresso Moka Pot 3-cup · €46 · ★4.4 (276) · anyone · ships 2d
  - `KD-005` Pour-Over Set · €78 · ★4.6 (183) · him · ships 3d
  - `KD-006` Burr Coffee Grinder, Manual · €115 · ★4.7 (241) · anyone · ships 3d

Review: 

## l1-057 · `get_product_details` `{"product_id": "kd-7"}`
*tolerant id: lower case, no zero padding*

- **product_id**: `"KD-007"`
- **in_stock_alternatives**:
  - `KD-004` Espresso Moka Pot 3-cup · €46 · ★4.4 (276) · anyone · ships 2d
  - `KD-005` Pour-Over Set · €78 · ★4.6 (183) · him · ships 3d
  - `KD-006` Burr Coffee Grinder, Manual · €115 · ★4.7 (241) · anyone · ships 3d

Review: 

## l1-058 · `get_product_details` `{"product_id": "KD024"}`
*tolerant id without dash; a cross-listed product resolves by either id*

- **product_id**: `"KD-024"`

Review: 

## l1-059 · `get_product_details` `{"product_id": "EX-001"}`
*unrated digital gift card*

- **product_id**: `"EX-001"`

Review: 

## l1-060 · `get_product_details` `{"product_id": "XX-999"}`
*unknown id is a recoverable error*

- **error_code**: `"product_not_found"`

Review: 

## l1-061 · `get_product_details` `{"product_id": "Chef's Knife"}`
*a name instead of an id is a recoverable error*

- **error_code**: `"product_not_found"`

Review: 
