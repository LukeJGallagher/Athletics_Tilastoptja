"""
Athletics Discipline Knowledge Base

Comprehensive reference for each athletics discipline including:
- Event descriptions and key success factors
- Qualification standards for major championships
- Target field sizes and ranking quotas
- World records and historical context

Used by the athletics dashboard for event documentation and qualification tracking.
"""

# Tokyo 2025 World Championships Entry Standards
# Source: https://citiusmag.com/articles/qualifying-standards-world-athletics-championships-tokyo-2025
TOKYO_2025_STANDARDS = {
    # Men's Track Events (times in seconds)
    '100m': {'men': 10.00, 'women': 11.07},
    '200m': {'men': 20.16, 'women': 22.57},
    '400m': {'men': 44.85, 'women': 50.75},
    '800m': {'men': 104.50, 'women': 119.00},  # 1:44.50 / 1:59.00
    '1500m': {'men': 213.00, 'women': 241.50},  # 3:33.00 / 4:01.50
    'Mile': {'men': 230.00, 'women': 259.90},  # 3:50.00 / 4:19.90
    '5000m': {'men': 781.00, 'women': 890.00},  # 13:01.00 / 14:50.00
    '10000m': {'men': 1620.00, 'women': 1820.00},  # 27:00.00 / 30:20.00
    '10,000m': {'men': 1620.00, 'women': 1820.00},
    'Marathon': {'men': 7590.00, 'women': 8610.00},  # 2:06:30 / 2:23:30
    '3000m Steeplechase': {'men': 495.00, 'women': 558.00},  # 8:15.00 / 9:18.00
    '110m Hurdles': {'men': 13.27, 'women': None},
    '100m Hurdles': {'men': None, 'women': 12.73},
    '400m Hurdles': {'men': 48.50, 'women': 54.65},
    '20km Race Walk': {'men': 4760.00, 'women': 5340.00},  # 1:19:20 / 1:29:00
    '35km Race Walk': {'men': 8880.00, 'women': 10080.00},  # 2:28:00 / 2:48:00

    # Men's Field Events (distances in meters, points for combined)
    'High Jump': {'men': 2.33, 'women': 1.97},
    'Pole Vault': {'men': 5.82, 'women': 4.73},
    'Long Jump': {'men': 8.27, 'women': 6.86},
    'Triple Jump': {'men': 17.22, 'women': 14.55},
    'Shot Put': {'men': 21.50, 'women': 18.80},
    'Discus Throw': {'men': 67.50, 'women': 64.50},
    'Hammer Throw': {'men': 78.20, 'women': 74.00},
    'Javelin Throw': {'men': 85.50, 'women': 64.00},
    'Decathlon': {'men': 8550, 'women': None},
    'Heptathlon': {'men': None, 'women': 6500},
}

# LA 2028 Olympics Entry Standards (Estimated - TBD by World Athletics)
# Based on Paris 2024 standards with typical adjustments
LA_2028_STANDARDS = {
    '100m': {'men': 10.00, 'women': 11.07},
    '200m': {'men': 20.16, 'women': 22.57},
    '400m': {'men': 44.90, 'women': 50.40},
    '800m': {'men': 103.50, 'women': 118.00},
    '1500m': {'men': 213.00, 'women': 240.00},
    '5000m': {'men': 780.00, 'women': 882.00},
    '10000m': {'men': 1620.00, 'women': 1800.00},
    'Marathon': {'men': 7590.00, 'women': 8460.00},
    '3000m Steeplechase': {'men': 503.00, 'women': 555.00},
    '110m Hurdles': {'men': 13.27, 'women': None},
    '100m Hurdles': {'men': None, 'women': 12.77},
    '400m Hurdles': {'men': 48.70, 'women': 54.85},
    '20km Race Walk': {'men': 4740.00, 'women': 5280.00},
    'High Jump': {'men': 2.33, 'women': 1.97},
    'Pole Vault': {'men': 5.82, 'women': 4.73},
    'Long Jump': {'men': 8.27, 'women': 6.86},
    'Triple Jump': {'men': 17.22, 'women': 14.55},
    'Shot Put': {'men': 21.35, 'women': 18.80},
    'Discus Throw': {'men': 67.20, 'women': 64.50},
    'Hammer Throw': {'men': 78.00, 'women': 74.00},
    'Javelin Throw': {'men': 85.50, 'women': 64.00},
    'Decathlon': {'men': 8460, 'women': None},
    'Heptathlon': {'men': None, 'women': 6480},
}

# Target field sizes and ranking quotas per event
# 50% qualify via entry standards, 50% via WA Rankings
EVENT_QUOTAS = {
    # Sprints
    '100m': {'total_field': 48, 'ranking_quota': 24},
    '200m': {'total_field': 48, 'ranking_quota': 24},
    '400m': {'total_field': 48, 'ranking_quota': 24},

    # Middle Distance
    '800m': {'total_field': 48, 'ranking_quota': 24},
    '1500m': {'total_field': 45, 'ranking_quota': 22},
    '5000m': {'total_field': 42, 'ranking_quota': 21},
    '10000m': {'total_field': 27, 'ranking_quota': 14},
    '10,000m': {'total_field': 27, 'ranking_quota': 14},

    # Hurdles
    '100m Hurdles': {'total_field': 40, 'ranking_quota': 20},
    '110m Hurdles': {'total_field': 40, 'ranking_quota': 20},
    '400m Hurdles': {'total_field': 40, 'ranking_quota': 20},

    # Steeplechase
    '3000m Steeplechase': {'total_field': 45, 'ranking_quota': 22},

    # Road Events
    'Marathon': {'total_field': 80, 'ranking_quota': 40},
    '20km Race Walk': {'total_field': 60, 'ranking_quota': 30},
    '35km Race Walk': {'total_field': 50, 'ranking_quota': 25},

    # Jumps
    'High Jump': {'total_field': 32, 'ranking_quota': 16},
    'Pole Vault': {'total_field': 32, 'ranking_quota': 16},
    'Long Jump': {'total_field': 32, 'ranking_quota': 16},
    'Triple Jump': {'total_field': 32, 'ranking_quota': 16},

    # Throws
    'Shot Put': {'total_field': 32, 'ranking_quota': 16},
    'Discus Throw': {'total_field': 32, 'ranking_quota': 16},
    'Hammer Throw': {'total_field': 32, 'ranking_quota': 16},
    'Javelin Throw': {'total_field': 32, 'ranking_quota': 16},

    # Combined Events
    'Decathlon': {'total_field': 24, 'ranking_quota': 12},
    'Heptathlon': {'total_field': 24, 'ranking_quota': 12},

    # Relays (top 16 teams)
    '4x100m Relay': {'total_field': 16, 'ranking_quota': 2},
    '4x400m Relay': {'total_field': 16, 'ranking_quota': 2},
    '4x400m Mixed Relay': {'total_field': 16, 'ranking_quota': 2},
}

# Comprehensive discipline knowledge base
DISCIPLINE_KNOWLEDGE = {
    # ============================================
    # SPRINTS
    # ============================================
    "100m": {
        "category": "Track - Sprints",
        "description": "The 100 metres is the shortest outdoor sprint distance in athletics. Athletes must react quickly to the starting gun and accelerate to maximum velocity, maintaining speed through the finish line.",
        "key_factors": [
            "Reaction time at the start",
            "Explosive power in the first 30m",
            "Maximum velocity phase (60-80m)",
            "Speed maintenance to finish"
        ],
        "technical_elements": [
            "Block start technique",
            "Drive phase (first 20-30m)",
            "Upright running mechanics",
            "Arm action and relaxation"
        ],
        "qualification_window": "Aug 1, 2024 - Aug 24, 2025",
        "world_record_men": "9.58 (Usain Bolt, Berlin 2009)",
        "world_record_women": "10.49 (Florence Griffith-Joyner, Indianapolis 1988)",
        "asian_record_men": "9.83 (Su Bingtian, CHN)",
        "asian_record_women": "10.79 (Li Xuemei, CHN)"
    },

    "200m": {
        "category": "Track - Sprints",
        "description": "The 200 metres combines the explosive speed of the 100m with the endurance to maintain velocity around the bend and through the straight.",
        "key_factors": [
            "Bend running technique",
            "Speed endurance",
            "Transition from bend to straight",
            "Finishing speed"
        ],
        "technical_elements": [
            "Staggered start positioning",
            "Lean into the bend",
            "Maintaining relaxation at high speed",
            "Float phase before finish"
        ],
        "qualification_window": "Aug 1, 2024 - Aug 24, 2025",
        "world_record_men": "19.19 (Usain Bolt, Berlin 2009)",
        "world_record_women": "21.34 (Florence Griffith-Joyner, Seoul 1988)",
        "asian_record_men": "19.88 (Xie Zhenye, CHN)",
        "asian_record_women": "22.01 (Li Xuemei, CHN)"
    },

    "400m": {
        "category": "Track - Sprints",
        "description": "The 400 metres is the longest sprint event, requiring a combination of speed, speed endurance, and race tactics. Often considered the most demanding sprint.",
        "key_factors": [
            "Pace distribution strategy",
            "Lactate tolerance",
            "Speed endurance",
            "Mental toughness in final 100m"
        ],
        "technical_elements": [
            "Controlled acceleration first 100m",
            "Relaxed running 100-200m",
            "Maintaining form 200-300m",
            "Fighting fatigue in final 100m"
        ],
        "qualification_window": "Aug 1, 2024 - Aug 24, 2025",
        "world_record_men": "43.03 (Wayde van Niekerk, Rio 2016)",
        "world_record_women": "47.60 (Marita Koch, Canberra 1985)",
        "asian_record_men": "44.65 (Femi Ogunode, QAT)",
        "asian_record_women": "49.68 (Wang Junxia, CHN)"
    },

    # ============================================
    # MIDDLE DISTANCE
    # ============================================
    "800m": {
        "category": "Track - Middle Distance",
        "description": "The 800 metres demands a rare combination of speed and endurance. Athletes must balance their energy output over two laps while positioning themselves for a fast finish.",
        "key_factors": [
            "Aerobic and anaerobic capacity",
            "Race tactics and positioning",
            "Kick speed in final 200m",
            "Lactate threshold"
        ],
        "technical_elements": [
            "Efficient running economy",
            "Tactical positioning on bends",
            "Pacing strategy",
            "Final sprint mechanics"
        ],
        "qualification_window": "Aug 1, 2024 - Aug 24, 2025",
        "world_record_men": "1:40.91 (David Rudisha, London 2012)",
        "world_record_women": "1:53.28 (Jarmila Kratochvilova, Munich 1983)",
        "asian_record_men": "1:42.79 (Mohammed Aman, ETH for QAT)",
        "asian_record_women": "1:55.54 (Liu Dong, CHN)"
    },

    "1500m": {
        "category": "Track - Middle Distance",
        "description": "The 1500 metres, known as the 'metric mile', is a tactical race requiring endurance, speed, and strategic racing. Finishing kick is often decisive.",
        "key_factors": [
            "Aerobic capacity",
            "Finishing speed (last 400m)",
            "Race reading and tactics",
            "Positional awareness"
        ],
        "technical_elements": [
            "Relaxed running at race pace",
            "Covering moves from competitors",
            "Timing the finishing kick",
            "Efficient stride at varied paces"
        ],
        "qualification_window": "Aug 1, 2024 - Aug 24, 2025",
        "world_record_men": "3:26.00 (Hicham El Guerrouj, Rome 1998)",
        "world_record_women": "3:49.11 (Faith Kipyegon, Paris 2023)",
        "asian_record_men": "3:29.14 (Rashid Ramzi, BRN)",
        "asian_record_women": "3:50.46 (Qu Yunxia, CHN)"
    },

    "5000m": {
        "category": "Track - Long Distance",
        "description": "The 5000 metres tests endurance over 12.5 laps. Modern races often feature fast finishes, requiring both stamina and speed.",
        "key_factors": [
            "Aerobic endurance",
            "Race tactics",
            "Speed over final 400-800m",
            "Heat management"
        ],
        "technical_elements": [
            "Efficient running economy",
            "Surge and recover tactics",
            "Drafting in packs",
            "Timing finishing kick"
        ],
        "qualification_window": "Aug 1, 2024 - Aug 24, 2025",
        "world_record_men": "12:35.36 (Joshua Cheptegei, Monaco 2020)",
        "world_record_women": "14:00.21 (Gudaf Tsegay, Eugene 2023)",
        "asian_record_men": "12:52.98 (Albert Rop, BRN)",
        "asian_record_women": "14:30.88 (Jiang Bo, CHN)"
    },

    "10000m": {
        "category": "Track - Long Distance",
        "description": "The 10,000 metres is the longest track event, covering 25 laps. It demands exceptional endurance and tactical awareness.",
        "key_factors": [
            "Aerobic capacity",
            "Heat and pacing management",
            "Mental endurance",
            "Finishing speed"
        ],
        "technical_elements": [
            "Consistent lap splits",
            "Pack running and drafting",
            "Surge and recover",
            "Final sprint preparation"
        ],
        "qualification_window": "Feb 25, 2024 - Aug 24, 2025",
        "world_record_men": "26:11.00 (Joshua Cheptegei, Valencia 2020)",
        "world_record_women": "28:54.14 (Almaz Ayana, Rio 2016)",
        "asian_record_men": "27:07.43 (Abdullah Ahmad Hassan, QAT)",
        "asian_record_women": "29:31.78 (Wang Junxia, CHN)"
    },

    # ============================================
    # HURDLES
    # ============================================
    "110m Hurdles": {
        "category": "Track - Hurdles",
        "description": "The 110m hurdles for men features 10 hurdles at 1.067m height. Athletes must combine sprinting speed with precise hurdling technique.",
        "key_factors": [
            "Sprint speed between hurdles",
            "Hurdle clearance efficiency",
            "3-step rhythm consistency",
            "Lead leg and trail leg technique"
        ],
        "technical_elements": [
            "8 steps to first hurdle",
            "3 steps between hurdles",
            "Attack the hurdle with lead leg",
            "Quick trail leg recovery"
        ],
        "qualification_window": "Aug 1, 2024 - Aug 24, 2025",
        "world_record_men": "12.80 (Aries Merritt, Brussels 2012)",
        "asian_record_men": "13.09 (Liu Xiang, CHN)"
    },

    "100m Hurdles": {
        "category": "Track - Hurdles",
        "description": "The 100m hurdles for women features 10 hurdles at 0.838m height. Requires explosive speed and technical precision.",
        "key_factors": [
            "Sprint speed",
            "Hurdle technique",
            "Rhythm and consistency",
            "Reaction time"
        ],
        "technical_elements": [
            "7-8 steps to first hurdle",
            "3 steps between hurdles",
            "Aggressive lead leg attack",
            "Efficient trail leg clearance"
        ],
        "qualification_window": "Aug 1, 2024 - Aug 24, 2025",
        "world_record_women": "12.12 (Kendra Harrison, London 2016)",
        "asian_record_women": "12.44 (Wu Shujiao, CHN)"
    },

    "400m Hurdles": {
        "category": "Track - Hurdles",
        "description": "The 400m hurdles combines the demands of the 400m flat with 10 hurdles. Stride patterns and fatigue management are crucial.",
        "key_factors": [
            "Speed endurance",
            "Stride pattern flexibility",
            "Hurdle technique under fatigue",
            "Lactate tolerance"
        ],
        "technical_elements": [
            "Steps to first hurdle",
            "Stride pattern between hurdles",
            "Alternating lead legs (for some)",
            "Maintaining technique when tired"
        ],
        "qualification_window": "Aug 1, 2024 - Aug 24, 2025",
        "world_record_men": "45.94 (Karsten Warholm, Tokyo 2020)",
        "world_record_women": "50.68 (Sydney McLaughlin-Levrone, Eugene 2022)",
        "asian_record_men": "47.79 (Abderrahman Samba, QAT)",
        "asian_record_women": "53.96 (Han Qing, CHN)"
    },

    "3000m Steeplechase": {
        "category": "Track - Hurdles",
        "description": "The 3000m steeplechase covers 7.5 laps with 28 barriers and 7 water jumps. Combines distance running with hurdling over fixed obstacles.",
        "key_factors": [
            "Aerobic endurance",
            "Barrier clearance technique",
            "Water jump efficiency",
            "Pace judgment"
        ],
        "technical_elements": [
            "Hurdle stride technique",
            "Water jump approach",
            "Recovering stride after barriers",
            "Positioning for barriers"
        ],
        "qualification_window": "Aug 1, 2024 - Aug 24, 2025",
        "world_record_men": "7:52.11 (Lamecha Girma, Paris 2024)",
        "world_record_women": "8:44.32 (Beatrice Chepkoech, Monaco 2018)",
        "asian_record_men": "8:00.38 (Hicham Bellani, MAR for BRN)",
        "asian_record_women": "9:09.63 (Ruth Jebet, BRN)"
    },

    # ============================================
    # JUMPS
    # ============================================
    "High Jump": {
        "category": "Field - Jumps",
        "description": "The high jump requires athletes to clear a horizontal bar using any technique. The Fosbury Flop is now universal at elite level.",
        "key_factors": [
            "Vertical leap ability",
            "Approach speed and curve",
            "Takeoff technique",
            "Bar clearance"
        ],
        "technical_elements": [
            "J-curve approach run",
            "Penultimate step lowering",
            "Vertical takeoff",
            "Arch over bar (Fosbury Flop)"
        ],
        "qualification_window": "Aug 1, 2024 - Aug 24, 2025",
        "world_record_men": "2.45 (Javier Sotomayor, Salamanca 1993)",
        "world_record_women": "2.09 (Stefka Kostadinova, Rome 1987)",
        "asian_record_men": "2.39 (Mutaz Essa Barshim, QAT)",
        "asian_record_women": "1.99 (Nicola Olyslagers, AUS for CHN)"
    },

    "Pole Vault": {
        "category": "Field - Jumps",
        "description": "The pole vault uses a flexible pole to propel athletes over a bar. It's the most technical field event, combining speed, gymnastics, and timing.",
        "key_factors": [
            "Approach speed",
            "Pole selection and carry",
            "Takeoff and penetration",
            "Inversion and bar clearance"
        ],
        "technical_elements": [
            "16-20 step approach",
            "Plant and takeoff timing",
            "Swing and extension",
            "Turn and push-off"
        ],
        "qualification_window": "Aug 1, 2024 - Aug 24, 2025",
        "world_record_men": "6.24 (Armand Duplantis, Xiamen 2024)",
        "world_record_women": "5.06 (Yelena Isinbayeva, Zurich 2009)",
        "asian_record_men": "5.92 (EJ Obiena, PHI)",
        "asian_record_women": "4.70 (Li Ling, CHN)"
    },

    "Long Jump": {
        "category": "Field - Jumps",
        "description": "The long jump measures horizontal distance from takeoff to landing. Athletes sprint down a runway and leap from a takeoff board.",
        "key_factors": [
            "Approach speed",
            "Takeoff accuracy",
            "Flight technique",
            "Landing efficiency"
        ],
        "technical_elements": [
            "Consistent approach run",
            "Penultimate stride preparation",
            "Takeoff angle and height",
            "Hitch-kick or hang technique"
        ],
        "qualification_window": "Aug 1, 2024 - Aug 24, 2025",
        "world_record_men": "8.95 (Mike Powell, Tokyo 1991)",
        "world_record_women": "7.52 (Galina Chistyakova, Leningrad 1988)",
        "asian_record_men": "8.47 (Mohammed Issa, KSA)",
        "asian_record_women": "7.01 (Yao Weili, CHN)"
    },

    "Triple Jump": {
        "category": "Field - Jumps",
        "description": "The triple jump consists of a hop, step, and jump sequence. Requires coordination of three distinct phases from a single approach.",
        "key_factors": [
            "Approach speed",
            "Phase ratio balance",
            "Takeoff consistency",
            "Maintaining velocity"
        ],
        "technical_elements": [
            "Hop (same leg takeoff and landing)",
            "Step (opposite leg)",
            "Jump (into pit)",
            "Active landings between phases"
        ],
        "qualification_window": "Aug 1, 2024 - Aug 24, 2025",
        "world_record_men": "18.29 (Jonathan Edwards, Gothenburg 1995)",
        "world_record_women": "15.67 (Yulimar Rojas, Tokyo 2020)",
        "asian_record_men": "17.59 (Li Yanxi, CHN)",
        "asian_record_women": "15.25 (Olga Rypakova, KAZ)"
    },

    # ============================================
    # THROWS
    # ============================================
    "Shot Put": {
        "category": "Field - Throws",
        "description": "The shot put involves throwing a heavy metal ball (7.26kg men, 4kg women) as far as possible from a 2.135m circle.",
        "key_factors": [
            "Explosive power",
            "Technique efficiency",
            "Release angle and speed",
            "Balance in circle"
        ],
        "technical_elements": [
            "Glide or rotational technique",
            "Power position",
            "Explosive hip drive",
            "Follow through and balance"
        ],
        "qualification_window": "Aug 1, 2024 - Aug 24, 2025",
        "world_record_men": "23.56 (Ryan Crouser, Los Angeles 2023)",
        "world_record_women": "22.63 (Natalya Lisovskaya, Moscow 1987)",
        "asian_record_men": "21.49 (Sultan Al-Dawoodi, KSA)",
        "asian_record_women": "21.76 (Gong Lijiao, CHN)"
    },

    "Discus Throw": {
        "category": "Field - Throws",
        "description": "The discus throw involves spinning and releasing a disc (2kg men, 1kg women) from a 2.5m circle.",
        "key_factors": [
            "Rotational speed",
            "Release technique",
            "Timing and rhythm",
            "Balance and control"
        ],
        "technical_elements": [
            "Initial wind-up",
            "1.5 rotation across circle",
            "Power position and release",
            "Discus aerodynamics"
        ],
        "qualification_window": "Aug 1, 2024 - Aug 24, 2025",
        "world_record_men": "74.08 (Jurgen Schult, Neubrandenburg 1986)",
        "world_record_women": "76.80 (Gabriele Reinsch, Neubrandenburg 1988)",
        "asian_record_men": "69.32 (Ehsan Hadadi, IRI)",
        "asian_record_women": "67.59 (Xiao Yanling, CHN)"
    },

    "Hammer Throw": {
        "category": "Field - Throws",
        "description": "The hammer throw involves spinning and releasing a metal ball (7.26kg men, 4kg women) attached to a wire and handle.",
        "key_factors": [
            "Rotational speed",
            "Balance during turns",
            "Release timing",
            "Wire tension control"
        ],
        "technical_elements": [
            "Preliminary swings",
            "Three or four turns",
            "Accelerating rotation",
            "Release at optimal angle"
        ],
        "qualification_window": "Aug 1, 2024 - Aug 24, 2025",
        "world_record_men": "86.74 (Yuriy Sedykh, Stuttgart 1986)",
        "world_record_women": "82.98 (Anita Wlodarczyk, Warsaw 2016)",
        "asian_record_men": "81.22 (Koji Murofushi, JPN)",
        "asian_record_women": "77.68 (Wang Zheng, CHN)"
    },

    "Javelin Throw": {
        "category": "Field - Throws",
        "description": "The javelin throw involves throwing a spear-like implement (800g men, 600g women) after an approach run.",
        "key_factors": [
            "Approach speed",
            "Throwing arm speed",
            "Release angle",
            "Javelin flight stability"
        ],
        "technical_elements": [
            "Approach run rhythm",
            "Cross-over steps",
            "Block and throw sequence",
            "Follow through"
        ],
        "qualification_window": "Aug 1, 2024 - Aug 24, 2025",
        "world_record_men": "98.48 (Jan Zelezny, Jena 1996)",
        "world_record_women": "72.28 (Barbora Spotakova, Stuttgart 2008)",
        "asian_record_men": "92.97 (Neeraj Chopra, IND)",
        "asian_record_women": "67.98 (Lyu Huihui, CHN)"
    },

    # ============================================
    # COMBINED EVENTS
    # ============================================
    "Decathlon": {
        "category": "Combined Events",
        "description": "The decathlon is a ten-event competition over two days for men. It tests all-around athletic ability across running, jumping, and throwing disciplines.",
        "events_day1": ["100m", "Long Jump", "Shot Put", "High Jump", "400m"],
        "events_day2": ["110m Hurdles", "Discus", "Pole Vault", "Javelin", "1500m"],
        "key_factors": [
            "Versatility across disciplines",
            "Recovery between events",
            "Consistency over two days",
            "Mental resilience"
        ],
        "qualification_window": "Feb 25, 2024 - Aug 24, 2025",
        "world_record_men": "9126 (Kevin Mayer, Talence 2018)",
        "asian_record_men": "8725 (Damian Warner, training in Asia)"
    },

    "Heptathlon": {
        "category": "Combined Events",
        "description": "The heptathlon is a seven-event competition over two days for women. It tests versatility across sprints, hurdles, jumps, and throws.",
        "events_day1": ["100m Hurdles", "High Jump", "Shot Put", "200m"],
        "events_day2": ["Long Jump", "Javelin", "800m"],
        "key_factors": [
            "All-around athletic ability",
            "Event-to-event transitions",
            "Energy management",
            "Technical consistency"
        ],
        "qualification_window": "Feb 25, 2024 - Aug 24, 2025",
        "world_record_women": "7291 (Jackie Joyner-Kersee, Seoul 1988)",
        "asian_record_women": "6750 (Hyleas Fountain, training record)"
    },

    # ============================================
    # ROAD EVENTS
    # ============================================
    "Marathon": {
        "category": "Road Events",
        "description": "The marathon covers 42.195 kilometers (26.2 miles). It's the ultimate test of endurance, pacing, and mental toughness.",
        "key_factors": [
            "Aerobic endurance",
            "Pacing strategy",
            "Nutrition and hydration",
            "Heat management"
        ],
        "technical_elements": [
            "Even pace distribution",
            "Efficient running form",
            "Fuel and hydration timing",
            "Mental focus in late stages"
        ],
        "qualification_window": "Nov 5, 2023 - May 4, 2025",
        "world_record_men": "2:00:35 (Kelvin Kiptum, Chicago 2023)",
        "world_record_women": "2:11:53 (Tigist Assefa, Berlin 2023)",
        "asian_record_men": "2:04:56 (Elhanbi Hamza, BRN)",
        "asian_record_women": "2:19:12 (Mizuki Noguchi, JPN)"
    },

    "20km Race Walk": {
        "category": "Race Walking",
        "description": "The 20km race walk requires athletes to maintain continuous contact with the ground and keep the supporting leg straight. Technical violations result in disqualification.",
        "key_factors": [
            "Walking technique compliance",
            "Aerobic endurance",
            "Pacing",
            "Heat tolerance"
        ],
        "technical_elements": [
            "Hip rotation",
            "Straight supporting leg",
            "Continuous ground contact",
            "Arm drive"
        ],
        "qualification_window": "Feb 25, 2024 - Aug 24, 2025",
        "world_record_men": "1:16:36 (Kento Ikeda, JPN, 2024)",
        "world_record_women": "1:23:49 (Jiayu Yang, CHN, 2021)",
        "asian_record_men": "1:16:36 (Kento Ikeda, JPN)",
        "asian_record_women": "1:23:49 (Jiayu Yang, CHN)"
    },

    "35km Race Walk": {
        "category": "Race Walking",
        "description": "The 35km race walk replaced the 50km walk as the longest race walking event. Tests extreme endurance while maintaining technical compliance.",
        "key_factors": [
            "Ultra-endurance",
            "Technical consistency over time",
            "Pacing strategy",
            "Nutrition timing"
        ],
        "qualification_window": "Nov 5, 2023 - May 4, 2025",
        "world_record_men": "2:21:44 (Masatora Kawano, JPN, 2023)",
        "world_record_women": "2:37:44 (Kimberly Garcia, PER, 2023)"
    },

    # ============================================
    # RELAYS
    # ============================================
    "4x100m Relay": {
        "category": "Relays",
        "description": "The 4x100m relay features four athletes each running 100m, passing a baton within designated exchange zones. Requires precise timing and coordination.",
        "key_factors": [
            "Individual sprint speed",
            "Baton exchange technique",
            "Exchange zone timing",
            "Team chemistry"
        ],
        "technical_elements": [
            "Outgoing runner acceleration",
            "Incoming runner timing",
            "Baton pass within zone",
            "Visual or blind exchange"
        ],
        "qualification": "Top 14 at World Relays + 2 from World List",
        "world_record_men": "36.84 (Jamaica, London 2012)",
        "world_record_women": "40.82 (USA, London 2012)"
    },

    "4x400m Relay": {
        "category": "Relays",
        "description": "The 4x400m relay features four athletes each running 400m. Exchange zones allow for running starts on legs 2-4.",
        "key_factors": [
            "Individual 400m speed",
            "Split distribution strategy",
            "Exchange timing",
            "Leg order optimization"
        ],
        "qualification": "Top 14 at World Relays + 2 from World List",
        "world_record_men": "2:54.29 (USA, London 1993)",
        "world_record_women": "3:15.17 (USSR, Seoul 1988)"
    },

    "4x400m Mixed Relay": {
        "category": "Relays",
        "description": "The mixed 4x400m relay features two men and two women per team, in any order. Introduced at World Championships in 2019.",
        "key_factors": [
            "Leg order strategy",
            "Gender split optimization",
            "Exchange efficiency",
            "Tactical flexibility"
        ],
        "qualification": "Top 14 at World Relays + 2 from World List",
        "world_record": "3:07.45 (USA, Tokyo 2020)"
    }
}


def get_event_standard(event_name, championship='tokyo_2025', gender='men'):
    """
    Get the entry standard for an event at a specific championship.

    Args:
        event_name: Name of the event (e.g., '100m', 'Long Jump')
        championship: 'tokyo_2025' or 'la_2028'
        gender: 'men' or 'women'

    Returns:
        float or None: The entry standard, or None if not found
    """
    standards = TOKYO_2025_STANDARDS if championship == 'tokyo_2025' else LA_2028_STANDARDS

    if event_name in standards:
        return standards[event_name].get(gender)

    # Try alternative event names
    alt_names = {
        '10000m': '10,000m',
        '10,000m': '10000m',
    }
    if event_name in alt_names and alt_names[event_name] in standards:
        return standards[alt_names[event_name]].get(gender)

    return None


def get_event_quota(event_name):
    """
    Get the target field size and ranking quota for an event.

    Args:
        event_name: Name of the event

    Returns:
        dict: {'total_field': int, 'ranking_quota': int} or default values
    """
    if event_name in EVENT_QUOTAS:
        return EVENT_QUOTAS[event_name]

    # Default quota for unknown events
    return {'total_field': 32, 'ranking_quota': 16}


def get_event_knowledge(event_name):
    """
    Get comprehensive knowledge about an event.

    Args:
        event_name: Name of the event

    Returns:
        dict: Event knowledge dictionary or None if not found
    """
    return DISCIPLINE_KNOWLEDGE.get(event_name)


def format_standard_for_display(value, event_name):
    """
    Format a standard value for display (e.g., seconds to MM:SS.ss).

    Args:
        value: The numeric value
        event_name: Event name to determine format

    Returns:
        str: Formatted string
    """
    if value is None:
        return "N/A"

    # Events measured in points
    if event_name in ['Decathlon', 'Heptathlon']:
        return f"{int(value)} pts"

    # Events measured in meters
    field_events = ['High Jump', 'Pole Vault', 'Long Jump', 'Triple Jump',
                    'Shot Put', 'Discus Throw', 'Hammer Throw', 'Javelin Throw']
    if event_name in field_events:
        return f"{value:.2f}m"

    # Time events
    if value >= 3600:  # Hours (marathon, etc.)
        hours = int(value // 3600)
        mins = int((value % 3600) // 60)
        secs = value % 60
        return f"{hours}:{mins:02d}:{secs:05.2f}"
    elif value >= 60:  # Minutes
        mins = int(value // 60)
        secs = value % 60
        return f"{mins}:{secs:05.2f}"
    else:  # Seconds only
        return f"{value:.2f}"
