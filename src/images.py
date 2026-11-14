"""Map every product to an illustration (Microsoft Fluent Emoji 3D, MIT licence).

Lookup order:
  1. item keyword in the product name (only for fresh/staple categories, where the
     product *is* the item: "Onion - Organically Grown" -> onion)
  2. product type (all 426 types mapped)
  3. category
Images live in static/emoji/<codepoint>.webp and are served by Streamlit static serving.
"""
import re
from functools import lru_cache
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent.parent / "static" / "emoji"

# Categories where a keyword in the name describes the product itself.
KEYWORD_CATEGORIES = {
    "Fruits & Vegetables", "Foodgrains, Oil & Masala", "Bakery, Cakes & Dairy",
    "Eggs, Meat & Fish", "Beverages",
}

# Ordered: more specific phrases first.
KEYWORDS = [
    ("green tea", "🍵"), ("juice", "🧃"), ("coconut water|tender coconut", "🥥"),
    ("coffee", "☕"), ("tea", "🍵"), ("milk", "🥛"), ("lassi|buttermilk|curd|yogurt|dahi", "🥛"),
    ("cheese", "🧀"), ("paneer|tofu", "🧀"), ("butter|ghee", "🧈"), ("bread|pav|bun", "🍞"),
    ("croissant", "🥐"), ("bagel", "🥯"), ("baguette", "🥖"), ("cake|muffin|pastr|brownie", "🧁"),
    ("cookie|biscuit|rusk", "🍪"), ("ice cream", "🍨"), ("egg", "🥚"),
    ("chicken", "🍗"), ("mutton|lamb|goat", "🍖"), ("pork|ham|bacon|sausage", "🥓"),
    ("prawn|shrimp", "🦐"), ("crab", "🦀"), ("fish|tuna|salmon|seer|pomfret|rohu", "🐟"),
    ("onion", "🧅"), ("garlic", "🧄"), ("ginger", "🫚"), ("tomato", "🍅"), ("potato", "🥔"),
    ("sweet potato", "🍠"), ("carrot", "🥕"), ("corn", "🌽"), ("broccoli", "🥦"),
    ("cucumber", "🥒"), ("capsicum|bell pepper", "🫑"), ("chilli|chili", "🌶️"),
    ("brinjal|eggplant", "🍆"), ("mushroom", "🍄"), ("lettuce|spinach|palak|methi|coriander|"
    "cabbage|kale|leaves|leafy|mint|curry leaves", "🥬"), ("cauliflower", "🥦"),
    ("beans|peas", "🫛"), ("avocado", "🥑"), ("olive", "🫒"), ("lemon|lime", "🍋"),
    ("orange|mosambi|citrus|kinnow", "🍊"), ("apple", "🍎"), ("pear", "🍐"), ("banana", "🍌"),
    ("mango", "🥭"), ("grape", "🍇"), ("watermelon", "🍉"), ("melon", "🍈"),
    ("pineapple", "🍍"), ("strawberr", "🍓"), ("blueberr|berr", "🫐"), ("cherr", "🍒"),
    ("kiwi", "🥝"), ("peach|plum|apricot", "🍑"), ("coconut", "🥥"),
    ("pomegranate|papaya|guava|sapota|chikoo|fig|dragon", "🍎"),
    ("rose|marigold|flower|jasmine", "🌹"), ("sprout|salad", "🥗"),
    ("rice|basmati|poha|idli", "🍚"), ("atta|flour|maida|besan|sooji|rava", "🌾"),
    ("dal|lentil|moong|toor|urad|chana|rajma|pulses", "🫘"), ("peanut|groundnut", "🥜"),
    ("almond|cashew|walnut|pista|raisin|dry fruit|dates|nut", "🥜"),
    ("oil", "🫗"), ("salt", "🧂"), ("sugar|jaggery|sweetener", "🍬"), ("honey", "🍯"),
    ("masala|spice|turmeric|pepper|cumin|jeera|haldi|powder", "🌶️"),
    ("water", "💧"), ("soda|cola|cold drink", "🥤"), ("energy|sports drink", "🥤"),
]
_KEYWORD_RE = [(re.compile(rf"\b(?:{k})", re.I), e) for k, e in KEYWORDS]

CATEGORY_EMOJI = {
    "Fruits & Vegetables": "🥦", "Foodgrains, Oil & Masala": "🌾", "Bakery, Cakes & Dairy": "🥛",
    "Beverages": "🧃", "Snacks & Branded Foods": "🍿", "Beauty & Hygiene": "🧴",
    "Cleaning & Household": "🧽", "Kitchen, Garden & Pets": "🍳", "Baby Care": "🍼",
    "Eggs, Meat & Fish": "🥚", "Gourmet & World Food": "🫒",
}

_TYPES = """
Diapers=🧷|Baby Bath=🛁|Baby Oil & Shampoo=🧴|Baby Creams & Lotions=🧴|Baby Wipes=🧻|Sippers & Bottles=🍼|
Soothers & Teethers=🍼|Baby Food=🥣|Baby Powder=🧴|Baby Health=💊|Maternity Personal Care=🤰|Infant Formula=🍼|
Baby Gift Sets=🎁|Organic Baby Food=🥣|Baby Oral Care=🪥|Baby Laundry=🧺|Baby Dishes & Utensils=🥄|
Maternity Health Supplements=💊|Bibs & Napkins=👶|Nursing Tools=🍼|Combs, Brushes, Clippers=🪮|
Other Baby Accessories=👶|Baby Toys=🧸|Nappies & Rash Cream=🧴|Baby Buds=🦻|
Flavoured, Soya Milk=🥛|Cheese=🧀|Tea Cakes & Slice Cakes=🍰|Bakery Biscuits, Cookies=🍪|Ice Creams=🍨|
Butter & Margarine=🧈|Paneer, Tofu & Cream=🧀|Rusks=🍞|Brown, Wheat & Multigrain=🍞|Premium Cookies=🍪|
Bread Sticks & Lavash=🥖|Croissants, Bagels=🥐|Muffins & Cup Cakes=🧁|Milk=🥛|Curd=🥛|Buttermilk & Lassi=🥛|
Yogurt & Shrikhand=🥛|Milk, White & Sandwich=🍞|Buns, Pavs & Pizza Base=🍕|Condensed, Powdered Milk=🥛|
Khari & Cream Rolls=🥐|Pastries & Brownies=🍰|Dairy Free (Vegan)=🌱|Gourmet Bread=🥖|Panini, Focaccia & Pita=🥙|
Birthday & Party Cakes=🎂|Cheese & Garlic Bread=🥖|Bagels & Baguette=🥯|
Face Care=🧴|Ayurveda=🌿|Shampoo & Conditioner=🧴|Bathing Bars & Soaps=🧼|Body Care=🧴|Men's Deodorants=🧴|
Aromatherapy=🕯️|Supplements & Proteins=💪|Hand Wash & Sanitizers=🧼|Eau De Toilette=🌸|Hair Oil & Serum=💆|
Shaving Care=🪒|Shower Gel & Body Wash=🚿|Women's Deodorants=🌸|Face & Body=🧴|Eau De Parfum=🌸|Toothpaste=🪥|
Face Masks & Safety Gears=😷|Bathing Accessories=🧽|Sanitary Napkins=🩸|Hair Color=💇|Toothbrush=🪥|
Body Sprays & Mists=🌸|Moustache & Beard Care=🧔|Tools & Accessories=💅|Lip Care=💄|Hair & Scalp Treatment=💆|
Everyday Medicine=💊|Hair Care & Styling=💇|Bath & Shower=🚿|Hair Removal=🪒|Sexual Wellness=❤️|Perfume=🌸|
Tampons & Menstrual Cups=🩸|Eye Care=👁️|Adult Diapers=🧷|Talcum Powder=🧴|Gift Sets=🎁|Intimate Wash & Care=🧴|
Mouthwash=🪥|Cotton & Ear Buds=🦻|Panty Liners=🩸|Antiseptics & Bandages=🩹|Bath Salts & Oils=🛁|Face=💄|
Attar=🌸|Eyes=👁️|Talc=🧴|Body Scrubs & Exfoliants=🧽|Hair Styling=💇|Electric Toothbrush=🪥|
Dry Shampoo & Conditioner=🧴|Combos & Gift Sets=🎁|Makeup Accessories=💄|Eau De Cologne=🌸|
Floss & Tongue Cleaner=🪥|Nails=💅|Lips=💄|Slimming Products=⚖️|
Juices=🧃|Leaf & Dust Tea=🍵|Green Tea=🍵|Tea Bags=🍵|Instant Coffee=☕|Syrups & Concentrates=🍹|
Exotic & Flavoured Tea=🫖|Kids (5+Yrs)=🥛|Cold Drinks=🥤|Ground Coffee=☕|Unsweetened, Cold Press=🧃|
Men & Women=🥛|Sports & Energy Drinks=🥤|Non Alcoholic Drinks=🍹|Children (2-5 Yrs)=🥛|Packaged Water=💧|
Soda & Cocktail Mix=🍹|Glucose Powder, Tablets=⚡|Icetea, Non Aerated Drink=🧋|Spring Water=💧|Diabetic Drinks=🥛|
Air Freshener=🌸|Laundry, Storage Baskets=🧺|Floor & Other Cleaners=🧽|Imported Cleaners=🧴|
Notebooks, Files, Folders=📒|Detergent Powder, Liquid=🧺|Mops, Wipers=🧹|Dustbins=🗑️|
Agarbatti, Incense Sticks=🪔|Utensil Scrub-Pad, Glove=🧽|Toilet Cleaners=🚽|Pen, Pencils=✏️|
Dust Cloth & Wipes=🧽|Mosquito Repellent=🦟|Buckets & Mugs=🪣|Disinfectant Spray & Cleaners=🧴|
Scissor, Glue & Tape=✂️|Other Pooja Needs=🪔|Paper Napkin, Tissue Box=🧻|Exam Pads & Pencil Box=✏️|
Candles & Match Box=🕯️|Toilet & Other Brushes=🚽|Insect Repellent=🪳|Toilet Paper=🧻|
Dishwash Liquids & Pastes=🍽️|Fabric Pre, Post Wash=👕|Games & Calculators=🧮|Hangers, Clips & Rope=👕|
Dishwash Bars & Powders=🍽️|Kitchen, Glass & Drain=🧽|Lamp & Lamp Oil=🪔|Brooms & Dust Pans=🧹|
Bath Stool, Basin & Sets=🪣|Garbage Bags=🗑️|Car Freshener=🚗|Colours & Crayons=🖍️|
Aluminium Foil, Clingwrap=🧻|Camphor & Wicks=🪔|Disposable Cups & Plates=🥤|Kitchen Rolls=🧻|
Electronic Accessories=🔌|Shoe Polish=👞|Caps, Balloons & Candles=🎈|Decorations=🎉|
Soap Cases & Dispensers=🧼|Other Plastic Ware=🪣|Detergent Bars=🧼|Wet Wipe, Pocket Tissues=🧻|
Pooja Thali & Bells=🔔|Car Polish & Cleaners=🚗|Gift Wraps & Bags=🎁|Metal, Furniture Cleaner=🧽|
Seasonal Accessories=☂️|Books & Magazines=📚|Erasers & Sharpeners=✏️|Holi Colours & Pichkari=🎨|
Chicken Sausages=🌭|Frozen Fish & Seafood=🐟|Pork & Ham=🥓|Canned Seafood=🥫|Fresh Fish=🐟|Farm Eggs=🥚|
Dry Fish=🐟|Frozen Mutton=🍖|Fresh Mutton=🍖|Other Eggs=🥚|Country Eggs=🥚|Protein Eggs=🥚|
Marinated Meat=🍖|Fresh & Frozen Pork=🥓|Organic Eggs=🥚|Prawns & Shrimps=🦐|Turkey & Duck=🦃|
Blended Masalas=🌶️|Powdered Spices=🌶️|Organic Masalas & Spices=🌶️|Organic Dals & Pulses=🫘|Whole Spices=🌶️|
Herbs & Seasoning=🌿|Other Dry Fruits=🥜|Other Edible Oils=🫗|Organic Flours=🌾|Organic Rice, Other Rice=🍚|
Basmati Rice=🍚|Rice & Other Flours=🌾|Ghee & Vanaspati=🧈|Cereals & Millets=🌾|Salts=🧂|Urad & Other Dals=🫘|
Toor, Channa & Moong Dal=🫘|Mukhwas=🌿|Sugar & Jaggery=🍬|Raw Rice=🍚|Organic Edible Oil, Ghee=🫗|
Organic Dry Fruits=🥜|Organic Sugar, Jaggery=🍬|Boiled & Steam Rice=🍚|Organic Millet & Flours=🌾|
Sunflower, Rice Bran Oil=🌻|Poha, Sabudana & Murmura=🍚|Sooji, Maida & Besan=🌾|Sugarfree Sweeteners=🍬|
Cashews=🥜|Cooking Pastes=🧄|Atta Whole Wheat=🌾|Blended Cooking Oils=🫗|Olive & Canola Oils=🫒|Almonds=🥜|
Gingelly Oil=🫗|Soya & Mustard Oils=🫗|Raisins=🍇|Groundnut Oil=🥜|
Cut & Peeled Veggies=🥕|Organic Vegetables=🥦|Apples & Pomegranate=🍎|Exotic Vegetables=🥑|Organic Fruits=🍎|
Leafy Vegetables=🥬|Exotic Fruits=🥝|Mangoes=🥭|Seasonal Fruits=🍊|Banana, Sapota & Papaya=🍌|
Cut Fruit, Tender Coconut=🥥|Beans, Brinjals & Okra=🍆|Kiwi, Melon, Citrus Fruit=🍊|Potato, Onion & Tomato=🥔|
Recipe Packs=🥗|Cucumber & Capsicum=🥒|Root Vegetables=🥕|Gourd, Pumpkin, Drumstick=🎃|
Indian & Exotic Herbs=🌿|Fresh Salads & Sprouts=🥗|Lemon, Ginger & Garlic=🍋|Cabbage & Cauliflower=🥬|
Other Flowers=💐|Marigold=🌼|Roses=🌹|Specialty=🥦|
Gourmet Tea & Tea Bags=🫖|Dry Fruits & Berries=🫐|Roasted Seeds & Nuts=🥜|Healthy, Baked Snacks=🥨|
Cookies, Biscotti, Wafer=🍪|Herbs, Seasonings & Rubs=🌿|Jams, Marmalade, Spreads=🍓|Thai & Asian Sauces=🥢|
Coffee & Pre-Mix=☕|Luxury Chocolates, Gifts=🍫|Flours & Pre-Mixes=🌾|Baking, Cake Decorations=🎂|
Marshmallow, Candy, Jelly=🍬|Pastas & Spaghetti=🍝|International Cheese=🧀|Nachos & Chips=🌮|
International Chocolates=🍫|Imported Noodles=🍜|Cereal & Granola Bars=🥣|Chocolate, Peanut Spread=🥜|
Honey & Maple Syrup=🍯|Olive, Jalapeno, Gherkin=🫒|Gourmet Juices & Drinks=🧃|Curry Paste, Coconut Milk=🥥|
Health Drinks=🥛|Gourmet Ice Cream=🍨|Exotic Sugar & Salt=🧂|Quinoa & Grains=🌾|Pure, Pomace Olive Oil=🫒|
Crackers & Digestive=🍘|Imported Oats & Porridge=🥣|Flavoured & Other Oils=🫗|Balsamic & Cider Vinegar=🍶|
Extra Virgin Olive Oil=🫒|Mustard & Cheese Sauces=🧀|Hummus, Cheese, Salsa Dip=🥙|Salad Dressings=🥗|
Tomatoes & Vegetables=🍅|Gourmet Popcorn=🍿|Aerated, Still, Sparkling=💧|Muesli & Rice Cakes=🥣|
Cooking Chocolate, Cocoa=🍫|Trail & Cocktail Mixes=🥜|Gourmet Flakes=🥣|Beans & Pulses=🫘|Cocktail Mixes=🍹|
Flavoured & Greek Yogurt=🥛|Organic & Cold Press Oil=🫗|Milk & Soya Drinks=🥛|Cream & Cheese Spreads=🧀|
Butter & Cream=🧈|Non-Alcoholic Beer, Wine=🍷|Tofu=🧀|Imported Soups=🍲|Jasmine & Sushi Rice=🍣|
Meats & Sausages=🌭|Wine & Rice Vinegar=🍶|Fruits & Pulps=🍑|Regular & White Vinegar=🍶|Fish & Tuna=🐟|
Baking Accessories=🧁|Canola & Rapeseed Oil=🫗|
Containers Sets=🫙|Glassware=🥛|Water & Fridge Bottles=🍶|Pet Meals & Treats=🐕|Lunch Boxes=🍱|
Cups, Mugs & Tumblers=☕|Steel Storage Containers=🫙|Plates & Bowls=🍽️|Kitchen Tools & Other Accessories=🥄|
Pressure Cookers=🍲|Kadai & Fry Pans=🍳|Tawa & Sauce Pan=🍳|Strainer, Ladle, Spatula=🥄|CFL & Led Bulbs=💡|
Battery & Electrical=🔋|Copper Utensils=🫖|Pet Cleaning & Grooming=🐈|Knives & Peelers=🔪|Steel Lunch Boxes=🍱|
Cutlery, Spoon & Fork=🍴|Choppers & Graters=🔪|Plates & Tumblers=🍽️|Dinner Sets=🍽️|Cook And Serve=🍲|
Racks & Holders=🧺|Wall Hooks & Hangers=🪝|Casserole=🍲|Pet Collars & Leashes=🦮|Cookware Sets=🍳|
Bowls & Vessels=🥣|Umbrella=☂️|Bakeware Accessories=🧁|Fertilizers & Pesticides=🌱|Pet Feeding Support=🐕|
Vacuum Flask=🍶|Pots, Planters & Trays=🪴|Baking Tools & Brushes=🧁|Pet Toys=🎾|Bakeware Moulds, Cutters=🧁|
Lighters=🔥|Cloth Dryer & Iron Table=👕|Gardening Tools=🌱|Health Supplements=💊|Gas Stove=🔥|Seeds & Sapling=🌱|
Namkeen & Savoury Snacks=🥨|Breakfast & Snack Mixes=🥣|Chips & Corn Snacks=🍟|Chocolates=🍫|
Heat & Eat Ready Meals=🍛|Cookies=🍪|Papads, Ready To Fry=🫓|Cream Biscuits & Wafers=🍪|
Granola & Cereal Bars=🥣|Frozen Veg Snacks=🥟|Home Baking=🧁|Choco & Nut Spread=🍫|Other Veg Pickle=🫙|
Tomato Ketchup & Sauces=🍅|Toffee, Candy & Lollypop=🍭|Marie, Health, Digestive=🍪|Frozen Non-Veg Snacks=🍗|
Honey=🍯|Lime & Mango Pickle=🫙|Oats & Porridge=🥣|Instant Noodles=🍜|Soups=🍲|Muesli=🥣|
Chilli & Soya Sauce=🌶️|Chutney Powder=🌶️|Kids Cereal=🥣|Flakes=🥣|Dessert Mixes=🍮|Tinned, Packed Sweets=🍬|
Mints & Chewing Gum=🍬|Jam, Conserve, Marmalade=🍓|Salted Biscuits=🍘|Mayonnaise=🥪|Frozen Vegetables=🥦|
Fresh Sweets=🍬|Pasta & Macaroni=🍝|Vermicelli=🍜|Glucose & Milk Biscuits=🍪|Dips & Dressings=🥙|
Frozen Indian Breads=🫓|Chikki & Gajjak=🥜|Instant Pasta=🍝|Hakka Noodles=🍜|Canned Food=🥫|Vinegar=🍶|
Cup Noodles=🍜|Non Veg Pickle=🫙|Gift Boxes=🎁
"""
TYPE_EMOJI = dict(
    pair.strip().rsplit("=", 1) for pair in _TYPES.replace("\n", "").split("|") if pair.strip()
)


def emoji_for(product: str, category: str, ptype: str) -> str:
    if category in KEYWORD_CATEGORIES:
        for rx, e in _KEYWORD_RE:
            if rx.search(product):
                return e
    return TYPE_EMOJI.get(ptype) or CATEGORY_EMOJI.get(category, "🛒")


def codepoint(emoji: str) -> str:
    """'🧅' -> '1f9c5'; variation selectors are dropped."""
    return "-".join(f"{ord(c):x}" for c in emoji if ord(c) != 0xFE0F)


@lru_cache(maxsize=None)
def image_path(emoji: str) -> str | None:
    """URL path (Streamlit static serving) for an emoji image, or None if missing."""
    cp = codepoint(emoji)
    for name in (cp, f"{cp}-fe0f"):
        if (STATIC_DIR / f"{name}.webp").exists():
            return f"app/static/emoji/{name}.webp"
    return None


def image_for(meta: dict) -> tuple[str, str | None]:
    """(emoji, image URL or None) for a product's metadata dict."""
    e = emoji_for(meta["product"], meta["category"], meta["type"])
    return e, image_path(e)
