import random

REGIONS_AND_COUNTIES = {
    "Central": {
        "code": "CEN",
        "counties": [
            (1, "Nyandarua"),
            (2, "Nyeri"),
            (3, "Kirinyaga"),
            (4, "Murang'a"),
            (5, "Kiambu"),
            (6, "Nairobi"),
        ],
    },
    "Coast": {
        "code": "CST",
        "counties": [
            (7, "Mombasa"),
            (8, "Kwale"),
            (9, "Kilifi"),
            (10, "Tana River"),
            (11, "Lamu"),
            (12, "Taita Taveta"),
        ],
    },
    "Eastern": {
        "code": "EST",
        "counties": [
            (13, "Marsabit"),
            (14, "Isiolo"),
            (15, "Meru"),
            (16, "Tharaka Nithi"),
            (17, "Embu"),
            (18, "Kitui"),
            (19, "Machakos"),
            (20, "Makueni"),
        ],
    },
    "North Eastern": {
        "code": "NET",
        "counties": [
            (21, "Garissa"),
            (22, "Wajir"),
            (23, "Mandera"),
        ],
    },
    "Nyanza": {
        "code": "NYZ",
        "counties": [
            (24, "Siaya"),
            (25, "Kisumu"),
            (26, "Homa Bay"),
            (27, "Migori"),
            (28, "Kisii"),
            (29, "Nyamira"),
        ],
    },
    "Rift Valley": {
        "code": "RVL",
        "counties": [
            (30, "Turkana"),
            (31, "West Pokot"),
            (32, "Samburu"),
            (33, "Trans Nzoia"),
            (34, "Uasin Gishu"),
            (35, "Elgeyo Marakwet"),
            (36, "Nandi"),
            (37, "Baringo"),
            (38, "Laikipia"),
            (39, "Nakuru"),
            (40, "Narok"),
            (41, "Kajiado"),
            (42, "Kericho"),
            (43, "Bomet"),
        ],
    },
    "Western": {
        "code": "WST",
        "counties": [
            (44, "Kakamega"),
            (45, "Vihiga"),
            (46, "Bungoma"),
            (47, "Busia"),
        ],
    },
}

DEFAULT_ADMIN = {
    "email": "admin@dimba.co.ke",
    "password": "Admin@2026",
    "first_name": "System",
    "last_name": "Admin",
}

TEAM_SUFFIXES = [
    "FC", "United", "Stars", "City", "Rangers",
    "Rovers", "Athletic", "Warriors", "Lions", "Eagles",
]

# ---------------------------------------------------------------------------
# Test data: teams, county admins, coaches, player name pools
# ---------------------------------------------------------------------------

# (region_name, team_name, county_name)
LEGACY_TEAMS = [
    # Central
    ("Central", "Kiambu FC", "Kiambu"),
    ("Central", "Nyeri National", "Nyeri"),
    ("Central", "Murang'a Seal", "Murang'a"),
    ("Central", "Kirinyaga Stars", "Kirinyaga"),
    # Coast
    ("Coast", "Bandari Youth", "Mombasa"),
    ("Coast", "Malindi Stars", "Kilifi"),
    ("Coast", "Kwale Rangers", "Kwale"),
    ("Coast", "Taita Hills FC", "Taita Taveta"),
    # North Eastern
    ("North Eastern", "Garissa FC", "Garissa"),
    ("North Eastern", "Wajir Stars", "Wajir"),
    ("North Eastern", "Mandera United", "Mandera"),
    # Eastern
    ("Eastern", "Machakos United", "Machakos"),
    ("Eastern", "Meru FC", "Meru"),
    ("Eastern", "Embu Lions", "Embu"),
    ("Eastern", "Kitui Stars", "Kitui"),
    # Nyanza
    ("Nyanza", "Kisumu All Stars", "Kisumu"),
    ("Nyanza", "Migori Youth", "Migori"),
    ("Nyanza", "Homa Bay United", "Homa Bay"),
    ("Nyanza", "Kisii FC", "Kisii"),
    # Rift Valley
    ("Rift Valley", "Eldoret City", "Uasin Gishu"),
    ("Rift Valley", "Nakuru All Stars", "Nakuru"),
    ("Rift Valley", "Narok United", "Narok"),
    ("Rift Valley", "Kericho FC", "Kericho"),
    # Western
    ("Western", "Kakamega Homeboyz", "Kakamega"),
    ("Western", "Vihiga United", "Vihiga"),
    ("Western", "Bungoma Stars", "Bungoma"),
    ("Western", "Busia FC", "Busia"),
]


def _generate_all_teams():
    """Generate 10 teams per county (470 total across 47 counties)."""
    teams = []
    for region_name, data in REGIONS_AND_COUNTIES.items():
        for _code, county_name in data["counties"]:
            for suffix in TEAM_SUFFIXES:
                base = county_name.replace("'", "")
                team_name = f"{base} {suffix}"
                teams.append((region_name, team_name, county_name))
    return teams

TEAMS = _generate_all_teams()

# County admin names — one per county (44 total), keyed by county name
COUNTY_ADMINS = {
    "Nyandarua": ("James", "Kimani"),
    "Nyeri": ("Peter", "Mwangi"),
    "Kirinyaga": ("John", "Njoroge"),
    "Murang'a": ("Samuel", "Kariuki"),
    "Kiambu": ("David", "Kamau"),
    "Nairobi": ("Daniel", "Ochieng"),
    "Mombasa": ("Ali", "Hassan"),
    "Kwale": ("Omar", "Mwinyi"),
    "Kilifi": ("Salim", "Kazungu"),
    "Tana River": ("Abdi", "Tana"),
    "Lamu": ("Mohammed", "Shee"),
    "Taita Taveta": ("Joseph", "Mwakio"),
    "Marsabit": ("Ibrahim", "Sora"),
    "Isiolo": ("Ahmed", "Golicha"),
    "Meru": ("Geoffrey", "Muthomi"),
    "Tharaka Nithi": ("Stanley", "Mugambi"),
    "Embu": ("Patrick", "Njiru"),
    "Kitui": ("Benedict", "Musyoka"),
    "Machakos": ("Stephen", "Mutua"),
    "Makueni": ("Charles", "Kilonzo"),
    "Garissa": ("Abdirahman", "Sheikh"),
    "Wajir": ("Hussein", "Adan"),
    "Mandera": ("Abdullahi", "Ali"),
    "Siaya": ("Otieno", "Ouma"),
    "Kisumu": ("George", "Onyango"),
    "Homa Bay": ("Tom", "Odhiambo"),
    "Migori": ("Walter", "Owino"),
    "Kisii": ("Evans", "Nyakundi"),
    "Nyamira": ("Kennedy", "Mogaka"),
    "Turkana": ("Ekalale", "Lokorikeju"),
    "West Pokot": ("Kimutai", "Pkemoi"),
    "Samburu": ("Lekishon", "Lemarti"),
    "Trans Nzoia": ("Wafula", "Simiyu"),
    "Uasin Gishu": ("Kipkoech", "Ruto"),
    "Elgeyo Marakwet": ("Kiplagat", "Keter"),
    "Nandi": ("Kipchirchir", "Kosgei"),
    "Baringo": ("Kibet", "Chesire"),
    "Laikipia": ("Martin", "Leshao"),
    "Nakuru": ("Francis", "Njuguna"),
    "Narok": ("Ole", "Ntimama"),
    "Kajiado": ("Tipis", "Lenku"),
    "Kericho": ("Langat", "Kirui"),
    "Bomet": ("Wesley", "Korir"),
    "Kakamega": ("Brian", "Wanyama"),
    "Vihiga": ("Kevin", "Mudavadi"),
    "Bungoma": ("Timothy", "Masinde"),
    "Busia": ("Michael", "Ojaamong"),
}

# Coach names — one per team, keyed by team name
LEGACY_COACHES = {
    "Kiambu FC": ("Wanjiru", "Kamau"),
    "Nyeri National": ("Benson", "Maina"),
    "Murang'a Seal": ("Anthony", "Ndung'u"),
    "Kirinyaga Stars": ("Simon", "Wachira"),
    "Bandari Youth": ("Hassan", "Abdalla"),
    "Malindi Stars": ("Bakari", "Ngala"),
    "Kwale Rangers": ("Rashid", "Mwacharo"),
    "Taita Hills FC": ("Mwandawiro", "Mghanga"),
    "Garissa FC": ("Mohamed", "Abdi"),
    "Wajir Stars": ("Yusuf", "Ibrahim"),
    "Mandera United": ("Osman", "Noor"),
    "Machakos United": ("Philip", "Kyalo"),
    "Meru FC": ("Julius", "Murungi"),
    "Embu Lions": ("Lawrence", "Nyaga"),
    "Kitui Stars": ("Vincent", "Mwikya"),
    "Kisumu All Stars": ("Opiyo", "Wandera"),
    "Migori Youth": ("Okoth", "Ogolla"),
    "Homa Bay United": ("Oluoch", "Oloo"),
    "Kisii FC": ("Nyandiko", "Onyancha"),
    "Eldoret City": ("Kiprono", "Bett"),
    "Nakuru All Stars": ("Kamau", "Ndirangu"),
    "Narok United": ("Nchoe", "Saitoti"),
    "Kericho FC": ("Cheruiyot", "Sang"),
    "Kakamega Homeboyz": ("Barasa", "Lunani"),
    "Vihiga United": ("Eshimuli", "Otiato"),
    "Bungoma Stars": ("Wekesa", "Wamalwa"),
    "Busia FC": ("Oduya", "Wandera"),
}

# Player name pools — diverse Kenyan ethnic names
FIRST_NAMES = [
    # Kikuyu
    "Kamau", "Mwangi", "Njoroge", "Kariuki", "Wainaina",
    "Githinji", "Muturi", "Irungu", "Nderitu", "Gichuru",
    # Luo
    "Ochieng", "Otieno", "Owino", "Odhiambo", "Ouma",
    "Opiyo", "Oluoch", "Odongo", "Okoth", "Onyango",
    # Kalenjin
    "Kipkoech", "Kiprono", "Kibet", "Kiplagat", "Kimutai",
    "Kipchoge", "Kosgei", "Cheruiyot", "Ruto", "Sang",
    # Luhya
    "Wanyama", "Barasa", "Wafula", "Simiyu", "Masinde",
    "Wekesa", "Lunani", "Makhanu", "Wamalwa", "Eshimuli",
    # Kamba
    "Mutua", "Musyoka", "Kyalo", "Mwikya", "Kilonzo",
    "Muema", "Nzioka", "Ndunda", "Makau", "Kioko",
    # Meru/Embu
    "Muthomi", "Mugambi", "Murungi", "Nyaga", "Njiru",
    "Kirimi", "Mwenda", "Gitonga", "Kaberia", "Mpuru",
    # Coast
    "Hassan", "Omar", "Salim", "Rashid", "Bakari",
    "Abdalla", "Kazungu", "Ngala", "Mwacharo", "Shee",
]

LAST_NAMES = [
    # Kikuyu
    "Wanjiru", "Muthoni", "Njeri", "Wairimu", "Nyambura",
    "Kimani", "Ngugi", "Macharia", "Githae", "Mugo",
    # Luo
    "Akinyi", "Adhiambo", "Awuor", "Anyango", "Ogola",
    "Obuya", "Atieno", "Olweny", "Ayieko", "Gor",
    # Kalenjin
    "Bett", "Keter", "Kirui", "Korir", "Rotich",
    "Tanui", "Kiptoo", "Chepkoech", "Jeptoo", "Lagat",
    # Luhya
    "Wanyonyi", "Oduya", "Miheso", "Sakwa", "Muyanga",
    "Ingosi", "Shikhule", "Ambani", "Osundwa", "Namisi",
    # Kamba
    "Nthenge", "Mutiso", "Mwendwa", "Kavyu", "Muli",
    "Wambua", "Kimanzi", "Maingi", "Katana", "Kalekye",
    # Meru/Embu
    "Mwiti", "Kiugu", "Mutethia", "Gatimbu", "Mbaka",
    "Kaaria", "Ntongai", "Murithi", "Riungu", "Gikunda",
    # Coast
    "Tsuma", "Karisa", "Mramba", "Baya", "Chengo",
    "Mwatela", "Kai", "Mwaro", "Charo", "Dzombo",
]


def _generate_all_coaches():
    """Generate a coach name for every team."""
    rng = random.Random(99)  # deterministic
    coaches = {}
    for _, team_name, _ in TEAMS:
        coaches[team_name] = (rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES))
    return coaches

COACHES = _generate_all_coaches()
