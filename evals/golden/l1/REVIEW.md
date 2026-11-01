# Level-1 golden set v5 · review sheet

For each case: is the expected result what the tool *should* return for this catalogue?
Mark `ok`, or write what is wrong. Prices in EUR; ✗ = out of stock.
Cases unchanged since v4 keep their approval and are marked `ok (v4)`.

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

Review: ok (v4)

## l1-002 · `get_products_by_category` `{"category": "kitchen-dining"}`
*default page: in stock only, best rated first, 5 items*

- **product_ids**:
  - `KD-001` Chef's Knife 20cm · €149 · ★4.8 (394) · anyone · ships 3d
  - `KD-013` Enamel Casserole 24cm · €189 · ★4.8 (312) · anyone · ships 5d
  - `KD-006` Burr Coffee Grinder, Manual · €115 · ★4.7 (241) · anyone · ships 3d
  - `KD-020` Salt & Pepper Mills, Pair · €92 · ★4.7 (176) · anyone · ships 4d
  - `KD-009` Crystal Whisky Glasses, Pair · €89 · ★4.7 (132) · him · ships 4d
- **total_matches**: `22`

Review: ok (v4)

## l1-003 · `get_products_by_category` `{"category": "Kitchen and Dining"}`
*category name in another spelling resolves to the slug*

- **product_ids**:
  - `KD-001` Chef's Knife 20cm · €149 · ★4.8 (394) · anyone · ships 3d
  - `KD-013` Enamel Casserole 24cm · €189 · ★4.8 (312) · anyone · ships 5d
  - `KD-006` Burr Coffee Grinder, Manual · €115 · ★4.7 (241) · anyone · ships 3d
  - `KD-020` Salt & Pepper Mills, Pair · €92 · ★4.7 (176) · anyone · ships 4d
  - `KD-009` Crystal Whisky Glasses, Pair · €89 · ★4.7 (132) · him · ships 4d
- **total_matches**: `22`

Review: ok (v4)

## l1-004 · `get_products_by_category` `{"category": "kitchen"}`
*one distinctive word resolves to its category*

- **product_ids**:
  - `KD-001` Chef's Knife 20cm · €149 · ★4.8 (394) · anyone · ships 3d
  - `KD-013` Enamel Casserole 24cm · €189 · ★4.8 (312) · anyone · ships 5d
  - `KD-006` Burr Coffee Grinder, Manual · €115 · ★4.7 (241) · anyone · ships 3d
  - `KD-020` Salt & Pepper Mills, Pair · €92 · ★4.7 (176) · anyone · ships 4d
  - `KD-009` Crystal Whisky Glasses, Pair · €89 · ★4.7 (132) · him · ships 4d
- **total_matches**: `22`

Review: ok (v4)

## l1-005 · `get_products_by_category` `{"category": "garden"}`
*unknown category is a recoverable error that points to the right call*

- **error_code**: `"unknown_category"`
- **allowed_values**: `["beauty-wellness", "books-stationery", "experiences", "games-puzzles", "home-living", "jewellery", "kids", "kitchen-dining", "outdoor-travel", "pets", "tech-gadgets"]`
- **did_you_mean**: `["home-living"]`
- **hint**: `"Call get_products_by_category with category 'home-living' and subcategory 'Garden'."`

*In v4: not reviewed yet.*

Review: 

## l1-006 · `get_products_by_category` `{"category": "home-living", "subcategory": "candles"}`
*subcategory filter, case-insensitive; out-of-stock candle reported*

- **product_ids**:
  - `HL-003` Ember Ceramic Candle · €42 · ★4.8 (431) · anyone · ships 2d
  - `HL-005` Trio Votive Set · €54 · ★4.5 (97) · anyone · ships 2d
- **total_matches**: `2`
- **out_of_stock_matches**:
  - ✗ `HL-004` Linen Fig Candle · €38 · ★4.7 (289) · her · ships 2d

Review: ok (v4)

## l1-007 · `get_products_by_category` `{"category": "home-living", "subcategory": "Lamps"}`
*unknown subcategory is a recoverable error; the lamps are listed under Lighting*

- **error_code**: `"unknown_subcategory"`
- **allowed_values**: `["Candles", "Decor", "Fragrance", "Garden", "Lighting", "Storage", "Textiles", "Vases"]`
- **did_you_mean**: `["Lighting"]`
- **hint**: `"Call get_products_by_category with category 'home-living' and subcategory 'Lighting'."`

*In v4: not reviewed yet.*

*v3 comment:* `did_you_mean` correcto. El hint es genérico; como en l1-005, nombraría la llamada: "Call get_products_by_category with category 'home-living' and subcategory 'Lighting'." Además remite a `allowed_values`: si ese campo no va en la respuesta, apunta a algo que no existe.

Review: 

## l1-008 · `get_products_by_category` `{"category": "pets", "subcategory": "cats"}`
*the only cat product is out of stock: empty page, reported, not hidden*

- **product_ids**: *(none)*
- **total_matches**: `0`
- **out_of_stock_matches**:
  - ✗ `PT-003` Cat Tree, Compact · €119 · ★4.0 (96) · pet · ships 6d

Review: ok (v4)

## l1-009 · `get_products_by_category` `{"category": "pets", "subcategory": "cats", "include_out_of_stock": true}`
*include_out_of_stock returns it*

- **product_ids**:
  - ✗ `PT-003` Cat Tree, Compact · €119 · ★4.0 (96) · pet · ships 6d
- **total_matches**: `1`

Review: ok (v4)

## l1-010 · `get_products_by_category` `{"category": "experiences"}`
*Experiences holds only the two gift cards*

- **product_ids**:
  - `EX-001` Gift Card, 50 EUR · €50 · no reviews (0) · anyone · ships 0d
  - `EX-002` Gift Card, 100 EUR · €100 · no reviews (0) · anyone · ships 0d
- **total_matches**: `2`

Review: ok (v4)

## l1-011 · `get_products_by_category` `{"category": "kitchen-dining", "max_price": 42}`
*max_price is inclusive: KD-024 costs exactly 42*

- **product_ids**:
  - `KD-024` Herb Garden Kit · €42 · ★4.1 (167) · anyone · ships 3d
- **total_matches**: `1`
- **suggestions**: `[{"change": "max_price", "to": 44.0, "would_match": 2}]`

Review: ok (v4)

## l1-012 · `get_products_by_category` `{"category": "kitchen-dining", "min_price": 50, "max_price": 70}`
*price range*

- **product_ids**:
  - `KD-002` Paring Knife 9cm · €69 · ★4.6 (148) · anyone · ships 3d
  - `KD-003` Knife Sharpening Stone · €54 · ★4.5 (96) · him · ships 3d
  - `KD-023` Amber Glass Tumbler Set · €56 · ★4.5 (86) · anyone · ships 4d
  - `KD-021` Tea Infuser Pot · €68 · ★4.3 (102) · her · ships 3d
  - `KD-012` Slate Cheese Board Set · €62 · ★4.2 (87) · anyone · ships 3d
- **total_matches**: `6`

Review: ok (v4)

## l1-013 · `get_products_by_category` `{"category": "jewellery", "recipient": "her"}`
*recipient includes products for anyone*

- **product_ids**:
  - `JW-001` Gold Vermeil Chain Necklace · €165 · ★4.6 (289) · her · ships 4d
  - `JW-003` Huggie Earrings, Pair · €89 · ★4.5 (217) · her · ships 3d
  - `JW-002` Pearl Pendant · €128 · ★4.4 (134) · her · ships 4d
  - `JW-004` Stud Set, Three Pairs · €112 · ★4.3 (96) · her · ships 3d
  - `JW-006` Stacking Rings, Set of Three · €96 · ★4.2 (143) · her · ships 4d
- **total_matches**: `5`
- **out_of_stock_matches**:
  - ✗ `JW-008` Bracelet, Woven Cord · €54 · ★3.8 (67) · anyone · ships 3d

Review: ok (v4)

## l1-014 · `get_products_by_category` `{"category": "home-living", "occasion": "housewarming", "max_price": 50}`
*occasion plus price*

- **product_ids**:
  - `HL-023` Terrazzo Coaster Set · €32 · ★4.4 (111) · anyone · ships 3d
  - `HL-018` Entry Tray, Walnut · €44 · ★4.4 (63) · him · ships 3d
  - `HL-007` Stoneware Vase, Squat · €49 · ★4.3 (51) · anyone · ships 4d
  - `HL-012` Reed Diffuser, Cedar · €46 · ★4.1 (118) · anyone · ships 2d
  - `HL-028` Linen Table Runner · €48 · ★4.0 (41) · her · ships 3d
- **total_matches**: `7`
- **over_budget_matches**:
  - `HL-019` Ceramic Planter, Medium · €52 · ★4.2 (94) · anyone · ships 4d
  - `HL-024` Amber Glass Tumbler Set · €56 · ★4.5 (86) · anyone · ships 4d

Review: ok (v4)

## l1-015 · `get_products_by_category` `{"category": "tech-gadgets", "max_shipping_days": 2}`
*deadline filter*

- **product_ids**:
  - `TG-006` E-Reader 7in Glare-Free · €199 · ★4.8 (923) · anyone · ships 2d
  - `TG-001` Wireless Headphones ANC · €279 · ★4.7 (842) · anyone · ships 2d
  - `TG-002` Wireless Earbuds Pro · €189 · ★4.5 (1204) · anyone · ships 2d
  - `TG-004` Portable Speaker, Waterproof · €99 · ★4.4 (676) · anyone · ships 2d
  - `TG-016` Laptop Stand, Folding · €64 · ★4.4 (214) · anyone · ships 2d
- **total_matches**: `14`

Review: ok (v4)

## l1-016 · `get_products_by_category` `{"category": "beauty-wellness", "exclude": "scent,fragrance,candle"}`
*exclusions by word*

- **product_ids**:
  - `BW-001` Silk Pillowcase Pair · €119 · ★4.7 (486) · her · ships 3d
  - `BW-004` Vitamin C Serum 30ml · €64 · ★4.6 (721) · her · ships 2d
  - `BW-007` Safety Razor Set · €89 · ★4.6 (231) · him · ships 3d
  - `BW-017` Yoga Mat, Cork · €98 · ★4.6 (187) · her · ships 4d
  - `BW-002` Weighted Eye Mask · €42 · ★4.5 (312) · her · ships 2d
- **total_matches**: `14`

Review: ok (v4)

## l1-017 · `get_products_by_category` `{"category": "kids", "max_price": 30}`
*nothing under 30 in Kids: empty page and the filter to drop*

- **product_ids**: *(none)*
- **total_matches**: `0`
- **suggestions**: `[{"change": "max_price", "to": 34.0, "would_match": 1}]`

Review: ok (v4)

## l1-018 · `get_products_by_category` `{"category": "jewellery", "recipient": "her", "occasion": "anniversary", "max_price": 100}`
*strict filters return few: suggestion names the filter to drop*

- **product_ids**: *(none)*
- **total_matches**: `0`
- **over_budget_matches**:
  - `JW-002` Pearl Pendant · €128 · ★4.4 (134) · her · ships 4d
  - `JW-001` Gold Vermeil Chain Necklace · €165 · ★4.6 (289) · her · ships 4d
- **suggestions**: `[{"change": "occasion", "to": null, "would_match": 2}, {"change": "max_price", "to": 128.0, "would_match": 1}]`

Review: ok (v4)

## l1-019 · `get_products_by_category` `{"category": "tech-gadgets", "sort": "price_asc"}`
*cheapest first*

- **product_ids**:
  - `TG-020` Film Twin Pack · €22 · ★4.1 (203) · anyone · ships 2d
  - `TG-013` Switch Sampler Pack · €24 · ★4.3 (127) · him · ships 2d
  - `TG-007` E-Reader Case, Fabric · €39 · ★4.2 (241) · anyone · ships 2d
  - `TG-018` Magnetic Wallet Stand · €45 · ★3.8 (164) · him · ships 2d
  - `TG-009` Smart Plug, Pack of Four · €54 · ★4.1 (527) · anyone · ships 2d
- **total_matches**: `24`

Review: ok (v4)

## l1-020 · `get_products_by_category` `{"category": "tech-gadgets", "sort": "price_desc"}`
*most expensive first*

- **product_ids**:
  - `TG-025` Bookshelf Speakers, Pair · €899 · ★4.9 (76) · him · ships 7d
  - `TG-005` Turntable, Belt Drive · €349 · ★4.6 (198) · him · ships 5d
  - `TG-024` Smart Ring, Sleep Tracking · €329 · ★3.9 (142) · anyone · ships 4d
  - `TG-001` Wireless Headphones ANC · €279 · ★4.7 (842) · anyone · ships 2d
  - `TG-006` E-Reader 7in Glare-Free · €199 · ★4.8 (923) · anyone · ships 2d
- **total_matches**: `24`

Review: ok (v4)

## l1-021 · `get_products_by_category` `{"category": "books-stationery", "sort": "popularity"}`
*popularity is review count*

- **product_ids**:
  - `BS-004` Hardcover Notebook A5, Dotted · €28 · ★4.6 (512) · anyone · ships 2d
  - `BS-010` Atlas of Remote Islands · €36 · ★4.8 (341) · anyone · ships 3d
  - `BS-001` Fountain Pen, Medium Nib · €129 · ★4.7 (264) · anyone · ships 3d
  - `BS-005` Notebook Trio A6 · €24 · ★4.3 (203) · anyone · ships 2d
  - `BS-009` The Art of Slow Cooking · €42 · ★4.6 (178) · anyone · ships 3d
- **total_matches**: `15`

Review: ok (v4)

## l1-022 · `get_products_by_category` `{"category": "home-living", "limit": 5, "offset": 5}`
*second page*

- **product_ids**:
  - `HL-015` Marble Bookends · €95 · ★4.6 (58) · him · ships 5d
  - `HL-014` Nordic Wall Clock · €89 · ★4.5 (132) · anyone · ships 4d
  - `HL-005` Trio Votive Set · €54 · ★4.5 (97) · anyone · ships 2d
  - `HL-024` Amber Glass Tumbler Set · €56 · ★4.5 (86) · anyone · ships 4d
  - `HL-010` Waffle Cotton Throw · €78 · ★4.4 (203) · anyone · ships 3d
- **total_matches**: `26`

Review: ok (v4)

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

Review: ok (v4)

## l1-024 · `get_products_by_category` `{"category": "home-living", "limit": 10, "offset": 10}`
*second page of ten; cross-listed HL-021 appears in Home & Living under its HL id*

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

Review: ok (v4)

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

Review: ok (v4)

## l1-026 · `search_products` `{"query": "chef knife", "max_price": 100}`
*specific request with no exact answer: the €149 chef's knife is reported over budget*

- **product_ids**:
  - `KD-002` Paring Knife 9cm · €69 · ★4.6 (148) · anyone · ships 3d
  - `KD-003` Knife Sharpening Stone · €54 · ★4.5 (96) · him · ships 3d
- **total_matches**: `2`
- **over_budget_matches**:
  - `KD-001` Chef's Knife 20cm · €149 · ★4.8 (394) · anyone · ships 3d
- **missing_terms**: `{"KD-002": ["chef"], "KD-003": ["chef"]}`
- **suggestions**: `[{"change": "max_price", "to": 149.0, "would_match": 3}]`

Review: ok (v4)

## l1-027 · `search_products` `{"query": "chef knife"}`
*the same request without a budget finds the chef's knife first*

- **product_ids**:
  - `KD-001` Chef's Knife 20cm · €149 · ★4.8 (394) · anyone · ships 3d
  - `KD-002` Paring Knife 9cm · €69 · ★4.6 (148) · anyone · ships 3d
  - `KD-003` Knife Sharpening Stone · €54 · ★4.5 (96) · him · ships 3d
- **total_matches**: `3`
- **missing_terms**: `{"KD-002": ["chef"], "KD-003": ["chef"]}`

Review: ok (v4)

## l1-028 · `search_products` `{"query": "city map jigsaw"}`
*a product asked for by name that is out of stock is reported, not hidden*

- **product_ids**:
  - `GP-006` Jigsaw 1000pc, Botanical · €32 · ★4.4 (276) · her · ships 2d
- **total_matches**: `1`
- **out_of_stock_matches**:
  - ✗ `GP-007` Jigsaw 1000pc, City Map · €32 · ★4.2 (194) · him · ships 2d
- **missing_terms**: `{"GP-006": ["city", "map"]}`

Review: ok (v4)

## l1-029 · `search_products` `{"query": "fig candle"}`
*out-of-stock fig candle reported; the in-stock trio with a fig scent is returned*

- **product_ids**:
  - `HL-005` Trio Votive Set · €54 · ★4.5 (97) · anyone · ships 2d
  - `HL-003` Ember Ceramic Candle · €42 · ★4.8 (431) · anyone · ships 2d
- **total_matches**: `2`
- **out_of_stock_matches**:
  - ✗ `HL-004` Linen Fig Candle · €38 · ★4.7 (289) · her · ships 2d
- **missing_terms**: `{"HL-003": ["fig"]}`

Review: ok (v4)

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

Review: ok (v4)

## l1-031 · `search_products` `{"query": "sony noise cancelling headphones"}`
*a brand the shop does not sell is reported as unmatched*

- **product_ids**:
  - `TG-001` Wireless Headphones ANC · €279 · ★4.7 (842) · anyone · ships 2d
  - `TG-002` Wireless Earbuds Pro · €189 · ★4.5 (1204) · anyone · ships 2d
  - `TG-003` Open-Ear Sport Buds · €129 · ★4.1 (317) · him · ships 2d
- **total_matches**: `3`
- **missing_terms**: `{"TG-001": ["sony"], "TG-002": ["sony"], "TG-003": ["sony", "anc"]}`
- **unmatched_terms**: `["sony"]`

Review: ok (v4)

## l1-032 · `search_products` `{"query": "iphone"}`
*nothing matches: empty, unmatched term, no invention*

- **product_ids**: *(none)*
- **total_matches**: `0`
- **unmatched_terms**: `["iphone"]`

Review: ok (v4)

## l1-033 · `search_products` `{"query": "cuchillo"}`
*a non-English word matches nothing: the agent must translate*

- **product_ids**: *(none)*
- **total_matches**: `0`
- **unmatched_terms**: `["cuchillo"]`

Review: ok (v4)

## l1-034 · `search_products` `{"query": "asdfghjkl"}`
*nonsense matches nothing*

- **product_ids**: *(none)*
- **total_matches**: `0`
- **unmatched_terms**: `["asdfghjkl"]`

Review: ok (v4)

## l1-035 · `search_products` `{"query": "herb garden kit"}`
*cross-listed product appears once, under its primary id*

- **product_ids**:
  - `HL-021` Herb Garden Kit · €42 · ★4.1 (167) · anyone · ships 3d
  - `HL-019` Ceramic Planter, Medium · €52 · ★4.2 (94) · anyone · ships 4d
  - `HL-020` Aurora Hanging Planter · €47 · ★4.0 (38) · anyone · ships 4d
- **total_matches**: `3`
- **missing_terms**: `{"HL-019": ["herb"], "HL-020": ["herb"]}`

Review: ok (v4)

## l1-036 · `search_products` `{"query": "amber glass tumbler"}`
*the second cross-listed product appears once, under its primary id*

- **product_ids**:
  - `HL-024` Amber Glass Tumbler Set · €56 · ★4.5 (86) · anyone · ships 4d
- **total_matches**: `1`

Review: ok (v4)

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

Review: ok (v4)

## l1-038 · `search_products` `{"query": "throw blanket", "exclude": "alpaca,wool,sheepskin"}`
*vegan-style exclusions on materials*

- **product_ids**:
  - `HL-010` Waffle Cotton Throw · €78 · ★4.4 (203) · anyone · ships 3d
  - `BW-016` Sauna Blanket · €399 · ★3.7 (58) · anyone · ships 7d
- **total_matches**: `2`
- **missing_terms**: `{"BW-016": ["throw"]}`

*In v4: not reviewed yet.*

*v3 comment:* Sigue sobrando `BW-016` Sauna Blanket: es un aparato de sauna por infrarrojos, no una manta de sofá (mismo caso que el molinillo de pimienta en l1-069). Quedaría solo `HL-010`; total_matches `1`. Y sobra la sugerencia `exclude → null`: las exclusiones son una restricción deliberada (vegana), no un filtro que el dependiente propondría quitar; lo que añade es HL-009 alpaca y OT-007 con lana.

Review: 

## l1-039 · `search_products` `{"query": "puzzle", "sort": "price_asc"}`
*explicit sort overrides relevance*

- **product_ids**:
  - `GP-006` Jigsaw 1000pc, Botanical · €32 · ★4.4 (276) · her · ships 2d
  - `GP-008` Metal Puzzle Set, Six · €38 · ★4.0 (151) · anyone · ships 2d
  - `GP-012` Escape Room in a Box · €44 · ★4.1 (208) · couple · ships 2d
  - `GP-005` Wooden Puzzle 500pc, Coastline · €78 · ★4.8 (163) · anyone · ships 4d
- **total_matches**: `4`
- **out_of_stock_matches**:
  - ✗ `GP-007` Jigsaw 1000pc, City Map · €32 · ★4.2 (194) · him · ships 2d

Review: ok (v4)

## l1-040 · `search_products` `{"query": "running"}`
*a hobby word that lives in tags*

- **product_ids**:
  - `TG-003` Open-Ear Sport Buds · €129 · ★4.1 (317) · him · ships 2d
- **total_matches**: `1`

Review: ok (v4)

## l1-041 · `search_products` `{"query": "pasta"}`
*pasta matches the pasta kit (the agent decides if the shopper meant money)*

- **product_ids**:
  - `KD-018` Handmade Pasta Bowls, Pair · €74 · ★4.6 (58) · couple · ships 4d
  - `KD-015` Pasta Making Kit · €98 · ★4.3 (93) · anyone · ships 4d
- **total_matches**: `2`

Review: ok (v4)

## l1-042 · `search_products` `{"query": "candle", "include_out_of_stock": true}`
*include_out_of_stock mixes them into the ranking*

- **product_ids**:
  - `HL-003` Ember Ceramic Candle · €42 · ★4.8 (431) · anyone · ships 2d
  - ✗ `HL-004` Linen Fig Candle · €38 · ★4.7 (289) · her · ships 2d
  - `HL-005` Trio Votive Set · €54 · ★4.5 (97) · anyone · ships 2d
- **total_matches**: `3`

Review: ok (v4)

## l1-043 · `search_products` `{"query": "travel", "recipient": "him", "max_shipping_days": 3}`
*recipient plus deadline*

- **product_ids**:
  - `OT-002` Travel Mug, Leakproof · €38 · ★4.4 (512) · anyone · ships 2d
  - `BS-010` Atlas of Remote Islands · €36 · ★4.8 (341) · anyone · ships 3d
  - `TG-001` Wireless Headphones ANC · €279 · ★4.7 (842) · anyone · ships 2d
  - `OT-005` Packing Cube Set · €52 · ★4.5 (368) · anyone · ships 2d
  - `TG-017` Power Bank 20000mAh · €69 · ★4.3 (738) · anyone · ships 2d
- **total_matches**: `6`

Review: ok (v4)

## l1-044 · `search_products` `{"query": "headphones", "max_price": 150}`
*every ANC option costs more than 150: over-budget matches*

- **product_ids**:
  - `TG-003` Open-Ear Sport Buds · €129 · ★4.1 (317) · him · ships 2d
- **total_matches**: `1`
- **over_budget_matches**:
  - `TG-001` Wireless Headphones ANC · €279 · ★4.7 (842) · anyone · ships 2d
  - `TG-002` Wireless Earbuds Pro · €189 · ★4.5 (1204) · anyone · ships 2d
- **suggestions**: `[{"change": "max_price", "to": 189.0, "would_match": 2}]`

*v3 comment:* Cambiaría el orden de over_budget_matches: `TG-002` Wireless Earbuds Pro (€189, 39 por encima) antes que `TG-001` (€279, 129 por encima), como en v2. Es la que la sugerencia `max_price: 189` ofrece y la primera que enseñaría a quien tiene €150.

Review: deferred to level 2 (ADR-006 freeze): over-budget earbuds before the dearer headphones

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
  - `BW-001` Silk Pillowcase Pair · €119 · ★4.7 (486) · her · ships 3d
  - `JW-002` Pearl Pendant · €128 · ★4.4 (134) · her · ships 4d

Review: ok (v4)

## l1-046 · `search_products` `{}`
*no query: best rated in the whole catalogue*

- **product_ids**:
  - `HL-009` Alpaca Throw · €185 · ★4.9 (156) · anyone · ships 5d
  - `TG-025` Bookshelf Speakers, Pair · €899 · ★4.9 (76) · him · ships 7d
  - `TG-006` E-Reader 7in Glare-Free · €199 · ★4.8 (923) · anyone · ships 2d
  - `HL-003` Ember Ceramic Candle · €42 · ★4.8 (431) · anyone · ships 2d
  - `KD-001` Chef's Knife 20cm · €149 · ★4.8 (394) · anyone · ships 3d
- **total_matches**: `139`

Review: ok (v4)

## l1-047 · `search_products` `{"sort": "price_asc"}`
*no query: the cheapest products in the catalogue*

- **product_ids**:
  - `BS-015` Letterpress Card, Single · €6.5 · ★3.6 (31) · anyone · ships 2d
  - `BS-012` Poetry Anthology, Pocket · €22 · ★4.3 (89) · her · ships 2d
  - `TG-020` Film Twin Pack · €22 · ★4.1 (203) · anyone · ships 2d
  - `BS-005` Notebook Trio A6 · €24 · ★4.3 (203) · anyone · ships 2d
  - `TG-013` Switch Sampler Pack · €24 · ★4.3 (127) · him · ships 2d
- **total_matches**: `139`

Review: ok (v4)

## l1-048 · `search_products` `{"sort": "popularity", "limit": 3}`
*no query: the most reviewed*

- **product_ids**:
  - `TG-002` Wireless Earbuds Pro · €189 · ★4.5 (1204) · anyone · ships 2d
  - `TG-006` E-Reader 7in Glare-Free · €199 · ★4.8 (923) · anyone · ships 2d
  - `TG-001` Wireless Headphones ANC · €279 · ★4.7 (842) · anyone · ships 2d
- **total_matches**: `139`

Review: ok (v4)

## l1-049 · `search_products` `{"recipient": "kids", "max_price": 40}`
*no query, filters only*

- **product_ids**:
  - `KI-003` Illustrated Story Collection · €34 · ★4.6 (213) · kids · ships 2d
  - `BS-010` Atlas of Remote Islands · €36 · ★4.8 (341) · anyone · ships 3d
  - `HL-027` Incense Set, Japanese · €28 · ★4.7 (224) · anyone · ships 2d
  - `BS-004` Hardcover Notebook A5, Dotted · €28 · ★4.6 (512) · anyone · ships 2d
  - `OT-002` Travel Mug, Leakproof · €38 · ★4.4 (512) · anyone · ships 2d
- **total_matches**: `17`
- **over_budget_matches**:
  - `KI-006` Night Light, Rechargeable · €42 · ★4.3 (241) · kids · ships 2d
  - `KI-005` Kids' Art Supply Case · €48 · ★4.4 (126) · kids · ships 3d

*In v4: deferred to level 2; the expected result changed.*

*v3 comment:* Mejor que v2: `over_budget_matches` con KI-006 y KI-005 cubre lo que faltaba. Sigue sobrando `HL-027` Incense Set (incienso con soporte, no apto para niños); en su lugar `GP-008` Metal Puzzle Set (€38).

Review: 

## l1-050 · `search_products` `{"max_shipping_days": 0}`
*same-day: only digital gift cards*

- **product_ids**:
  - `EX-001` Gift Card, 50 EUR · €50 · no reviews (0) · anyone · ships 0d
  - `EX-002` Gift Card, 100 EUR · €100 · no reviews (0) · anyone · ships 0d
- **total_matches**: `2`
- **suggestions**: `[{"change": "max_shipping_days", "to": null, "would_match": 139}]`

Review: ok (v4)

## l1-051 · `search_products` `{"max_price": 10}`
*almost nothing under 10*

- **product_ids**:
  - `BS-015` Letterpress Card, Single · €6.5 · ★3.6 (31) · anyone · ships 2d
- **total_matches**: `1`
- **suggestions**: `[{"change": "max_price", "to": 22.0, "would_match": 3}]`

Review: ok (v4)

## l1-052 · `search_products` `{"min_price": 300}`
*only the most expensive items*

- **product_ids**:
  - `TG-025` Bookshelf Speakers, Pair · €899 · ★4.9 (76) · him · ships 7d
  - `TG-005` Turntable, Belt Drive · €349 · ★4.6 (198) · him · ships 5d
  - `TG-024` Smart Ring, Sleep Tracking · €329 · ★3.9 (142) · anyone · ships 4d
  - `BW-016` Sauna Blanket · €399 · ★3.7 (58) · anyone · ships 7d
- **total_matches**: `4`
- **suggestions**: `[{"change": "min_price", "to": 279.0, "would_match": 5}]`

Review: ok (v4)

## l1-053 · `get_product_details` `{"product_id": "KD-001"}`
*an in-stock product: no alternatives block*

- **product_id**: `"KD-001"`

Review: ok (v4)

## l1-054 · `get_product_details` `{"product_id": "HL-004"}`
*out of stock: in-stock alternatives from the same subcategory first*

- **product_id**: `"HL-004"`
- **in_stock_alternatives**:
  - `HL-003` Ember Ceramic Candle · €42 · ★4.8 (431) · anyone · ships 2d
  - `HL-005` Trio Votive Set · €54 · ★4.5 (97) · anyone · ships 2d
  - `HL-013` Room Spray Duo · €34 · ★3.9 (45) · anyone · ships 2d

Review: ok (v4)

## l1-055 · `get_product_details` `{"product_id": "PT-003"}`
*out of stock with no sibling in its subcategory: alternatives from its category*

- **product_id**: `"PT-003"`
- **in_stock_alternatives**:
  - `PT-001` Dog Bed, Orthopaedic · €149 · ★4.5 (178) · pet · ships 5d
  - `PT-002` Rope Toy Bundle · €28 · ★4.1 (264) · pet · ships 2d

Review: ok (v4)

## l1-056 · `get_product_details` `{"product_id": "KD-007"}`
*out-of-stock coffee product: alternatives closest in price*

- **product_id**: `"KD-007"`
- **in_stock_alternatives**:
  - `KD-004` Espresso Moka Pot 3-cup · €46 · ★4.4 (276) · anyone · ships 2d
  - `KD-005` Pour-Over Set · €78 · ★4.6 (183) · him · ships 3d
  - `KD-006` Burr Coffee Grinder, Manual · €115 · ★4.7 (241) · anyone · ships 3d

Review: ok (v4)

## l1-057 · `get_product_details` `{"product_id": "kd-7"}`
*tolerant id: lower case, no zero padding*

- **product_id**: `"KD-007"`
- **in_stock_alternatives**:
  - `KD-004` Espresso Moka Pot 3-cup · €46 · ★4.4 (276) · anyone · ships 2d
  - `KD-005` Pour-Over Set · €78 · ★4.6 (183) · him · ships 3d
  - `KD-006` Burr Coffee Grinder, Manual · €115 · ★4.7 (241) · anyone · ships 3d

Review: ok (v4)

## l1-058 · `get_product_details` `{"product_id": "KD024"}`
*tolerant id without dash; a cross-listed product resolves by either id*

- **product_id**: `"KD-024"`

Review: ok (v4)

## l1-059 · `get_product_details` `{"product_id": "EX-001"}`
*unrated digital gift card*

- **product_id**: `"EX-001"`

Review: ok (v4)

## l1-060 · `get_product_details` `{"product_id": "XX-999"}`
*unknown id is a recoverable error*

- **error_code**: `"product_not_found"`
- **allowed_values**: `[]`
- **did_you_mean**: `[]`
- **hint**: `"Product ids look like 'KD-001'. To find a product by name or description, use search_products."`

*In v4: not reviewed yet.*

Review: 

## l1-061 · `get_product_details` `{"product_id": "Chef's Knife"}`
*a name instead of an id is a recoverable error*

- **error_code**: `"product_not_found"`
- **allowed_values**: `[]`
- **did_you_mean**:
  - `KD-001` Chef's Knife 20cm · €149 · ★4.8 (394) · anyone · ships 3d
- **hint**: `"Product ids look like 'KD-001'. To find a product by name or description, use search_products."`

*In v4: not reviewed yet.*

Review: 

## l1-062 · `search_products` `{"query": "wooden board game"}`
*held out: three words; products matching more of them first*

- **product_ids**:
  - `GP-001` Strategy Board Game, Trade Routes · €64 · ★4.7 (588) · anyone · ships 3d
  - `GP-003` Two-Player Card Game · €26 · ★4.6 (417) · couple · ships 2d
  - `GP-002` Cooperative Game, Deep Water · €52 · ★4.5 (342) · anyone · ships 3d
  - `GP-004` Party Game, Eighty Prompts · €34 · ★3.9 (229) · anyone · ships 2d
  - `GP-012` Escape Room in a Box · €44 · ★4.1 (208) · couple · ships 2d
- **total_matches**: `8`
- **out_of_stock_matches**:
  - ✗ `TG-022` Handheld Game Console, Retro · €189 · ★4.6 (394) · him · ships 4d
- **missing_terms**: `{"GP-003": ["wooden"], "GP-002": ["wooden"], "GP-004": ["wooden"], "GP-012": ["wooden"], "TG-022": ["wooden", "board"]}`

*In v4: not reviewed yet.*

*v3 comment:* Mejor que v2 (fuera KI-002). Faltan en la página `GP-009` Chess Set, Weighted (€145, tablero y piezas de nogal y arce, el juego de mesa de madera por excelencia) y `GP-010` Backgammon Roll-Up (€89, madera); irían 2º y 3º, por delante de los juegos de cartas GP-003 y GP-004. Propuesta: GP-001, GP-009, GP-010, GP-002, GP-003. Sigue sobrando `TG-022` en out_of_stock_matches: es una consola, no un juego de mesa.

Review: 

## l1-063 · `search_products` `{"query": "scented gift", "recipient": "her", "max_price": 60}`
*held out: word plus filters*

- **product_ids**:
  - `HL-003` Ember Ceramic Candle · €42 · ★4.8 (431) · anyone · ships 2d
  - `HL-005` Trio Votive Set · €54 · ★4.5 (97) · anyone · ships 2d
  - `BW-005` Hand Cream Trio · €36 · ★4.3 (254) · anyone · ships 2d
  - `HL-012` Reed Diffuser, Cedar · €46 · ★4.1 (118) · anyone · ships 2d
  - `HL-013` Room Spray Duo · €34 · ★3.9 (45) · anyone · ships 2d
- **total_matches**: `7`
- **out_of_stock_matches**:
  - ✗ `HL-004` Linen Fig Candle · €38 · ★4.7 (289) · her · ships 2d

*v3 comment:* Orden corregido (HL-003, HL-005, BW-005 arriba). Cambiaría `HL-013` Room Spray Duo (★3.9) por `HL-027` Incense Set, Japanese (€28, ★4.7): el incienso es un regalo perfumado aunque no lleve la palabra "scented". Propuesta: HL-003, HL-005, BW-005, HL-027, HL-012.

Review: deferred to level 2 (ADR-006 freeze): incense as a scented gift

## l1-064 · `search_products` `{"query": "leather notebook"}`
*held out: material word and product word*

- **product_ids**:
  - `BS-006` Leather Journal Cover A5 · €95 · ★4.5 (87) · him · ships 4d
  - `BS-004` Hardcover Notebook A5, Dotted · €28 · ★4.6 (512) · anyone · ships 2d
  - `BS-005` Notebook Trio A6 · €24 · ★4.3 (203) · anyone · ships 2d
- **total_matches**: `3`
- **missing_terms**: `{"BS-004": ["leather"], "BS-005": ["leather"]}`

Review: ok (v4)

## l1-065 · `search_products` `{"query": "tea set", "max_price": 50}`
*held out: two common words under a budget*

- **product_ids**:
  - `KD-022` Loose Leaf Tea Flight · €44 · ★4.2 (138) · anyone · ships 2d
- **total_matches**: `1`
- **over_budget_matches**:
  - `KD-021` Tea Infuser Pot · €68 · ★4.3 (102) · her · ships 3d
- **suggestions**: `[{"change": "max_price", "to": 68.0, "would_match": 2}]`

Review: ok (v4)

## l1-066 · `search_products` `{"query": "wireless speaker", "max_price": 120}`
*held out: product type with a budget*

- **product_ids**:
  - `TG-004` Portable Speaker, Waterproof · €99 · ★4.4 (676) · anyone · ships 2d
- **total_matches**: `1`
- **suggestions**: `[{"change": "max_price", "to": 899.0, "would_match": 2}]`

*In v4: not reviewed yet.*

*v3 comment:* `missing_terms` de TG-004 está mal: es Bluetooth, o sea inalámbrico; marcarle "wireless" como ausente haría que el agente diga que no lo es. Sobran `TG-025` en over_budget_matches (altavoces pasivos con cable que necesitan amplificador, no inalámbricos) y la sugerencia `max_price: 899`. Quedaría solo TG-004, sin missing_terms, sin over_budget ni sugerencia.

Review: 

## l1-067 · `get_products_by_category` `{"category": "outdoor-travel", "recipient": "him"}`
*held out: recipient filter on a browse*

- **product_ids**:
  - `OT-004` Weekender Bag · €189 · ★4.7 (243) · him · ships 4d
  - `OT-009` Head Torch, Rechargeable · €54 · ★4.3 (312) · him · ships 2d
  - `OT-001` Insulated Bottle 750ml · €42 · ★4.6 (834) · anyone · ships 2d
  - `OT-005` Packing Cube Set · €52 · ★4.5 (368) · anyone · ships 2d
  - `OT-002` Travel Mug, Leakproof · €38 · ★4.4 (512) · anyone · ships 2d
- **total_matches**: `7`
- **out_of_stock_matches**:
  - ✗ `OT-008` Camping Hammock · €68 · ★4.5 (221) · him · ships 3d

Review: ok (v4)

## l1-068 · `search_products` `{"query": "silver earrings", "max_price": 80}`
*held out: material and product word, budget*

- **product_ids**: *(none)*
- **total_matches**: `0`
- **over_budget_matches**:
  - `JW-003` Huggie Earrings, Pair · €89 · ★4.5 (217) · her · ships 3d
  - `JW-004` Stud Set, Three Pairs · €112 · ★4.3 (96) · her · ships 3d
- **missing_terms**: `{"JW-003": ["silver"], "JW-004": ["silver"]}`
- **suggestions**: `[{"change": "max_price", "to": 89.0, "would_match": 1}]`

*In v4: not reviewed yet.*

*v3 comment:* Vacío y presupuesto correctos, pero JW-003 y JW-004 son de vermeil dorado, no de plata: en over_budget_matches deberían llevar `missing_terms` `{"JW-003": ["silver"], "JW-004": ["silver"]}`, o el agente los ofrecerá como pendientes de plata. El catálogo no tiene pendientes de plata.

Review: 

## l1-069 · `search_products` `{"query": "coffee grinder"}`
*held out: the first word is itself a kind of product*

- **product_ids**:
  - `KD-006` Burr Coffee Grinder, Manual · €115 · ★4.7 (241) · anyone · ships 3d
  - `KD-020` Salt & Pepper Mills, Pair · €92 · ★4.7 (176) · anyone · ships 4d
- **total_matches**: `2`
- **missing_terms**: `{"KD-020": ["coffee"]}`

*v3 comment:* Sobra `KD-020` Salt & Pepper Mills: un molinillo de pimienta no es un molinillo de café (mismo criterio que los vasos de whisky en 036). Quedaría solo `KD-006`; total_matches `1`, sin missing_terms.

Review: deferred to level 2 (ADR-006 freeze): a pepper mill for 'coffee grinder' (marked missing 'coffee')

## l1-070 · `search_products` `{"query": "wooden toy", "recipient": "kids"}`
*held out: material and product word, recipient*

- **product_ids**:
  - `KI-001` Wooden Building Blocks, 60pc · €78 · ★4.7 (264) · kids · ships 3d
  - `KI-002` Balance Board · €96 · ★4.5 (187) · kids · ships 4d
  - `KI-006` Night Light, Rechargeable · €42 · ★4.3 (241) · kids · ships 2d
  - `KI-004` Junior Science Kit · €62 · ★4.2 (158) · kids · ships 3d
- **total_matches**: `4`
- **missing_terms**: `{"KI-006": ["wooden"], "KI-004": ["wooden"]}`
- **suggestions**: `[{"change": "recipient", "to": null, "would_match": 5}]`

*In v4: deferred to level 2; the expected result changed.*

*v3 comment:* Sobra `PT-002` Rope Toy Bundle: es un juguete para perros. Quedaría KI-001, KI-002, KI-006, KI-004; total_matches `4`.

Review: 

## l1-071 · `search_products` `{"query": "travel pillow"}`
*held out: a product word the catalogue may not use*

- **product_ids**:
  - `OT-002` Travel Mug, Leakproof · €38 · ★4.4 (512) · anyone · ships 2d
  - `BS-010` Atlas of Remote Islands · €36 · ★4.8 (341) · anyone · ships 3d
  - `TG-001` Wireless Headphones ANC · €279 · ★4.7 (842) · anyone · ships 2d
  - `OT-004` Weekender Bag · €189 · ★4.7 (243) · him · ships 4d
  - `GP-003` Two-Player Card Game · €26 · ★4.6 (417) · couple · ships 2d
- **total_matches**: `10`
- **out_of_stock_matches**:
  - ✗ `BW-012` Acupressure Mat Set · €72 · ★4.0 (289) · anyone · ships 4d
- **missing_terms**: `{"OT-002": ["pillow"], "BS-010": ["pillow"], "TG-001": ["pillow"], "OT-004": ["pillow"], "GP-003": ["pillow"], "BW-012": ["travel"]}`

*In v4: not reviewed yet.*

*v3 comment:* El catálogo no tiene almohada de viaje, y una taza, un atlas, unos auriculares, una bolsa y un juego de cartas no lo son: solo coinciden por "travel", falta la palabra que dice qué producto es (al revés que en l1-064). Debería volver vacío (total_matches `0`) y dejar al agente decir que no hay; como mucho, el más cercano para dormir viajando es `BW-002` Weighted Eye Mask. Sobra también `BW-012` en out_of_stock_matches: es una esterilla de acupresión, su cojín no es de viaje.

Review: 

## l1-072 · `get_products_by_category` `{"category": "jewellery", "recipient": "her", "max_price": 60}`
*held out: browse, recipient and budget*

- **product_ids**: *(none)*
- **total_matches**: `0`
- **out_of_stock_matches**:
  - ✗ `JW-008` Bracelet, Woven Cord · €54 · ★3.8 (67) · anyone · ships 3d
- **over_budget_matches**:
  - `JW-003` Huggie Earrings, Pair · €89 · ★4.5 (217) · her · ships 3d
  - `JW-006` Stacking Rings, Set of Three · €96 · ★4.2 (143) · her · ships 4d
- **suggestions**: `[{"change": "max_price", "to": 89.0, "would_match": 1}]`

Review: ok (v4)

## l1-073 · `search_products` `{"query": "anniversary", "recipient": "him,couple", "max_price": 120}`
*held out: two recipients*

- **product_ids**:
  - `KD-009` Crystal Whisky Glasses, Pair · €89 · ★4.7 (132) · him · ships 4d
  - `GP-003` Two-Player Card Game · €26 · ★4.6 (417) · couple · ships 2d
  - `KD-018` Handmade Pasta Bowls, Pair · €74 · ★4.6 (58) · couple · ships 4d
  - `BS-006` Leather Journal Cover A5 · €95 · ★4.5 (87) · him · ships 4d
  - `BW-015` Turkish Bath Towel Set · €86 · ★4.4 (141) · couple · ships 4d
- **total_matches**: `15`
- **over_budget_matches**:
  - `KD-008` Cocktail Kit, Ten-Piece · €129 · ★4.5 (158) · him · ships 4d
  - `GP-009` Chess Set, Weighted · €145 · ★4.7 (124) · him · ships 5d

Review: ok (v4)

## l1-074 · `search_products` `{"query": "anniversary", "recipient": "her,couple", "max_price": 100}`
*a partner: her and couple*

- **product_ids**:
  - `GP-003` Two-Player Card Game · €26 · ★4.6 (417) · couple · ships 2d
  - `KD-018` Handmade Pasta Bowls, Pair · €74 · ★4.6 (58) · couple · ships 4d
  - `BW-015` Turkish Bath Towel Set · €86 · ★4.4 (141) · couple · ships 4d
  - `OT-007` Picnic Blanket, Waterproof · €74 · ★4.2 (154) · couple · ships 3d
  - `GP-012` Escape Room in a Box · €44 · ★4.1 (208) · couple · ships 2d
- **total_matches**: `11`
- **over_budget_matches**:
  - `BW-001` Silk Pillowcase Pair · €119 · ★4.7 (486) · her · ships 3d
  - `JW-002` Pearl Pendant · €128 · ★4.4 (134) · her · ships 4d

Review: ok (v4)

## l1-075 · `search_products` `{"query": "chef's knife"}`
*an apostrophe in the query: the possessive reads as its word*

- **product_ids**:
  - `KD-001` Chef's Knife 20cm · €149 · ★4.8 (394) · anyone · ships 3d
  - `KD-002` Paring Knife 9cm · €69 · ★4.6 (148) · anyone · ships 3d
  - `KD-003` Knife Sharpening Stone · €54 · ★4.5 (96) · him · ships 3d
- **total_matches**: `3`
- **missing_terms**: `{"KD-002": ["chef"], "KD-003": ["chef"]}`

*New in this version.*

Review: 

## l1-076 · `search_products` `{"query": "toy", "recipient": "kids", "max_price": 30}`
*a dog toy is for a pet, not for kids*

- **product_ids**: *(none)*
- **total_matches**: `0`
- **over_budget_matches**:
  - `KI-006` Night Light, Rechargeable · €42 · ★4.3 (241) · kids · ships 2d
  - `KI-004` Junior Science Kit · €62 · ★4.2 (158) · kids · ships 3d
- **suggestions**: `[{"change": "max_price", "to": 42.0, "would_match": 1}, {"change": "recipient", "to": null, "would_match": 1}]`

*New in this version.*

Review: 

## l1-077 · `search_products` `{"recipient": "pet"}`
*a pet gets pet products only, not the ones for any person*

- **product_ids**:
  - `PT-001` Dog Bed, Orthopaedic · €149 · ★4.5 (178) · pet · ships 5d
  - `PT-002` Rope Toy Bundle · €28 · ★4.1 (264) · pet · ships 2d
- **total_matches**: `2`
- **out_of_stock_matches**:
  - ✗ `PT-003` Cat Tree, Compact · €119 · ★4.0 (96) · pet · ships 6d
- **suggestions**: `[{"change": "recipient", "to": null, "would_match": 139}]`

*New in this version.*

Review: 

## l1-078 · `search_products` `{"query": "gardening", "recipient": "him", "max_price": 60}`
*the activity finds the Garden subcategory through a synonym*

- **product_ids**:
  - `HL-021` Herb Garden Kit · €42 · ★4.1 (167) · anyone · ships 3d
  - `HL-019` Ceramic Planter, Medium · €52 · ★4.2 (94) · anyone · ships 4d
  - `HL-020` Aurora Hanging Planter · €47 · ★4.0 (38) · anyone · ships 4d
- **total_matches**: `3`
- **suggestions**: `[{"change": "max_price", "to": 99.0, "would_match": 4}]`

*New in this version.*

Review: 

## l1-079 · `search_products` `{"query": "cooking", "recipient": "her", "max_price": 50}`
*the activity finds the cookbook, the herb kit and the kitchen aisle*

- **product_ids**:
  - `BS-009` The Art of Slow Cooking · €42 · ★4.6 (178) · anyone · ships 3d
  - `HL-021` Herb Garden Kit · €42 · ★4.1 (167) · anyone · ships 3d
  - `KD-004` Espresso Moka Pot 3-cup · €46 · ★4.4 (276) · anyone · ships 2d
  - `KD-022` Loose Leaf Tea Flight · €44 · ★4.2 (138) · anyone · ships 2d
- **total_matches**: `4`
- **suggestions**: `[{"change": "max_price", "to": 62.0, "would_match": 5}]`

*New in this version.*

Review: 

## l1-080 · `search_products` `{"query": "tech gadget", "recipient": "kids", "max_price": 100}`
*a category word: the tech aisle, after the products that say tech*

- **product_ids**:
  - `TG-010` Sunrise Alarm Clock · €89 · ★4.5 (412) · anyone · ships 3d
  - `TG-023` Noise Machine · €58 · ★4.2 (268) · anyone · ships 2d
  - `TG-009` Smart Plug, Pack of Four · €54 · ★4.1 (527) · anyone · ships 2d
  - `TG-015` Monitor Light Bar · €96 · ★4.5 (331) · anyone · ships 3d
  - `TG-004` Portable Speaker, Waterproof · €99 · ★4.4 (676) · anyone · ships 2d
- **total_matches**: `10`
- **over_budget_matches**:
  - `TG-011` Air Quality Monitor · €139 · ★4.0 (96) · anyone · ships 3d
  - `TG-008` Digital Photo Frame 10in · €169 · ★4.3 (384) · anyone · ships 3d

*New in this version.*

Review: 

## l1-081 · `search_products` `{"query": "kitchen", "max_price": 60}`
*a category word: the aisle after the product tagged kitchen*

- **product_ids**:
  - `HL-021` Herb Garden Kit · €42 · ★4.1 (167) · anyone · ships 3d
  - `BS-009` The Art of Slow Cooking · €42 · ★4.6 (178) · anyone · ships 3d
  - `KD-003` Knife Sharpening Stone · €54 · ★4.5 (96) · him · ships 3d
  - `KD-004` Espresso Moka Pot 3-cup · €46 · ★4.4 (276) · anyone · ships 2d
  - `KD-022` Loose Leaf Tea Flight · €44 · ★4.2 (138) · anyone · ships 2d
- **total_matches**: `5`
- **out_of_stock_matches**:
  - ✗ `KD-007` Cold Brew Carafe · €52 · ★4.1 (74) · anyone · ships 3d
  - ✗ `KD-019` Copper Measuring Cups · €58 · ★4.0 (42) · her · ships 3d

*New in this version.*

Review: 
