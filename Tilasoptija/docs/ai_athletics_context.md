# AI Athletics Context Document

Comprehensive reference for the athletics coaching chatbot. This document contains the complete domain knowledge, database schema, qualification standards, championship identifiers, and query guidelines needed to power an intelligent athletics coaching assistant focused on Saudi Arabian athletes and international competition analysis.

---

## 1. Database Schema

### Table Name: `athletics_data`

IMPORTANT: You MUST use ONLY these column names in SQL queries. The data has been pre-processed and columns renamed from the raw CSV format.

### Column Reference (USE THESE EXACT NAMES)

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `Athlete_Name` | TEXT | Full name (first + last) | Moukhled Al-Outaibi |
| `firstname` | TEXT | First name only | Moukhled |
| `lastname` | TEXT | Last name only | Al-Outaibi |
| `Athlete_ID` | TEXT | Unique athlete identifier | 32072 |
| `Athlete_CountryCode` | TEXT | 3-letter WA country code | KSA, USA, JPN |
| `Athlete_Country` | TEXT | Full country name | Saudi Arabia |
| `Gender` | TEXT | **Men** or **Women** (NOT M/F) | Men |
| `gender` | TEXT | Original M/F value | M |
| `Event` | TEXT | Event name | 100m, Long Jump, 4x400m Relay |
| `eventcode` | TEXT | Event code number | 100, LJ, 400H |
| `Result` | TEXT | Raw result string | 10.23, 1:45.67, 8.15 |
| `result_numeric` | REAL | Numeric result for sorting/comparison | 10.23, 105.67, 8.15 |
| `Competition` | TEXT | Full competition name | 33rd Olympic Games |
| `Competition_ID` | TEXT | Unique competition identifier | 13079218 |
| `Start_Date` | TEXT | Competition date (YYYY-MM-DD) | 2024-08-05 |
| `year` | INTEGER | Year extracted from date | 2024 |
| `Venue` | TEXT | Venue city | Paris |
| `Venue_CountryCode` | TEXT | Host country code | FRA |
| `Venue_Country` | TEXT | Full host country name | France |
| `Round` | TEXT | Round name (readable) | Final, Heat 1, Semi 2 |
| `round_normalized` | TEXT | Standardized round | Final, Semi Finals, Heats |
| `Position` | TEXT | Finishing position | 1, 2, 3 |
| `terrain` | TEXT | Indoor or Outdoor | Outdoor, Indoor |
| `timing` | TEXT | Timing method (often empty for FAT) | |
| `wind` | TEXT | Wind speed (m/s) | 2.6, -0.3 |
| `windlegal` | TEXT | Wind legality | Wind Assisted, Wind Legal |
| `wapoints` | REAL | World Athletics points score | 1105.0, 913.0 |
| `PB` | TEXT | Personal Best flag | PB or empty |
| `SB` | TEXT | Season Best flag | SB or empty |
| `Personal_Best` | TEXT | Same as PB (renamed) | PB or empty |
| `Date_of_Birth` | TEXT | Date of birth (YYYY-MM-DD) | 1999-03-15 |
| `yearofbirth` | TEXT | Birth year | 1999 |
| `agegroup` | TEXT | Age group | Sen, U20, U18 |
| `Row_id` | TEXT | Auto-increment row ID | 23921 |

### CRITICAL Column Name Rules

- Country filtering: Use `Athlete_CountryCode` (NOT nationality)
- Event filtering: Use `Event` (NOT eventname)
- Result text: Use `Result` (NOT performance)
- Gender filtering: Use `Gender` with values **'Men'** or **'Women'** (NOT 'M'/'F')
- Numeric sorting: Use `result_numeric` (REAL type, for comparisons)
- Competition name: Use `Competition` (NOT competitionname)
- Competition date: Use `Start_Date` (NOT competitiondate)
- Athlete name: Use `Athlete_Name` (or `firstname`/`lastname` separately)

---

## 2. Event Classification

### Complete EVENT_TYPE_MAP

Events are classified into three types that determine sort direction and comparison logic:

- **time** - Lower is better (track events, race walks, relays)
- **distance** - Higher is better (jumps, throws)
- **points** - Higher is better (combined events like decathlon, heptathlon)

#### Time Events (lower is better)
Sprints: 50m, 55m, 60m, 100m, 150m, 200m, 300m, 400m
Middle Distance: 500m, 600m, 800m, 1000m, 1200m, 1500m, 1600m, Mile, 2000m
Long Distance: 3000m, 5000m, 10000m/10,000m
Road: Marathon, Half Marathon, 5km Road, 10km Road, 15km Road, 20km Road, 25km Road, 30km Road
Hurdles: 60m Hurdles, 100m Hurdles (W), 110m Hurdles (M), 400m Hurdles (+ all height variants)
Steeplechase: 1500m/2000m/3000m Steeplechase
Relays: 4x100m, 4x200m, 4x400m, 4x400m Mixed, 4x800m, 4x1500m (+ format variants like "4 x 100m")
Race Walk: 3000m-50km Race Walk variants

#### Distance Events (higher is better)
Jumps: High Jump, Pole Vault, Long Jump, Triple Jump (+ Indoor variants)
Throws: Shot Put, Discus Throw, Hammer Throw, Javelin Throw (+ weight variants)

#### Points Events (higher is better)
Combined: Decathlon, Heptathlon, Pentathlon, Octathlon (+ youth/indoor variants)

---

## 3. Championship IDs

### MAJOR_COMPETITIONS_CID (Full Reference)

Each championship has a unique numeric Competition ID (CID) in the Tilastopaja database. Use these to filter results to specific major competitions.

#### Olympics (11 editions: 1984-2024)

| Year | City | CID |
|------|------|-----|
| 2024 | Paris | 13079218 |
| 2021 | Tokyo | 12992925 |
| 2016 | Rio de Janeiro | 12877460 |
| 2012 | London | 12825110 |
| 2008 | Beijing | 12042259 |
| 2004 | Athens | 8232064 |
| 2000 | Sydney | 8257021 |
| 1996 | Atlanta | 12828534 |
| 1992 | Barcelona | 12828528 |
| 1988 | Seoul | 12828533 |
| 1984 | Los Angeles | 12828557 |

#### World Championships (19 editions: 1983-2025)

| Year | City | CID |
|------|------|-----|
| 2025 | Tokyo | 13112510 |
| 2023 | Budapest | 13046619 |
| 2022 | Oregon (Eugene) | 13002354 |
| 2019 | Doha | 12935526 |
| 2017 | London | 12898707 |
| 2013 | Moscow | 12844203 |
| 2011 | Daegu | 12814135 |
| 2009 | Berlin | 12789100 |
| 2007 | Osaka | 10626603 |
| 2005 | Helsinki | 8906660 |
| 2003 | Paris | 7993620 |
| 2001 | Edmonton | 8257083 |
| 1999 | Seville | 8256922 |
| 1997 | Athens | 12996366 |
| 1995 | Gothenburg | 12828581 |
| 1993 | Stuttgart | 12828580 |
| 1991 | Tokyo | 12996365 |
| 1987 | Rome | 12996362 |
| 1983 | Helsinki | 8255184 |

#### World Athletics Indoor Championships (10 editions: 2006-2025)

| Year | City | CID |
|------|------|-----|
| 2025 | Nanjing | 13092360 |
| 2024 | Glasgow | 13056938 |
| 2022 | Belgrade | 13002200 |
| 2018 | Birmingham | 12904540 |
| 2016 | Portland | 12871065 |
| 2014 | Sopot | 12848482 |
| 2012 | Istanbul | 12821019 |
| 2010 | Doha | 12794620 |
| 2008 | Valencia | 11465020 |
| 2006 | Moscow | 9050779 |

#### World U20 Championships (11 editions: 2000-2024)

| Year | City | CID |
|------|------|-----|
| 2024 | Lima | 13080252 |
| 2022 | Cali | 13002364 |
| 2021 | Nairobi | 12993802 |
| 2018 | Tampere | 12910467 |
| 2016 | Bydgoszcz | 12876812 |
| 2014 | Eugene | 12853328 |
| 2012 | Barcelona | 12824526 |
| 2008 | Bydgoszcz | 11909738 |
| 2006 | Beijing | 9238748 |
| 2004 | Grosseto | 8196283 |
| 2000 | Santiago | 8256856 |

#### Asian Games (3 editions: 2014-2023)

| Year | City | CID |
|------|------|-----|
| 2023 | Hangzhou | 13048549 |
| 2018 | Jakarta | 12911586 |
| 2014 | Incheon | 12854365 |

#### Asian Athletics Championships (10 editions: 2003-2025)

| Year | City | CID |
|------|------|-----|
| 2025 | Gumi | 13105634 |
| 2023 | Bangkok | 13045167 |
| 2019 | Doha | 12927085 |
| 2017 | Bhubaneswar | 12897142 |
| 2015 | Wuhan | 12861120 |
| 2013 | Pune | 12843333 |
| 2011 | Kobe | 12812847 |
| 2007 | Amman | 10571413 |
| 2005 | Incheon | 8923929 |
| 2003 | Manila | 7999347 |

#### Asian Indoor Championships (7 editions: 2008-2025)

| Year | City | CID |
|------|------|-----|
| 2025 | Hangzhou | 13092359 |
| 2023 | Astana | 13048100 |
| 2018 | Tehran | 12908028 |
| 2016 | Doha | 12869866 |
| 2014 | Hangzhou | 12847848 |
| 2012 | Hangzhou | 12822308 |
| 2008 | Doha | 11466050 |

#### Youth Olympics (3 editions: 2010-2018)

| Year | City | CID |
|------|------|-----|
| 2018 | Buenos Aires | 12912645 |
| 2014 | Nanjing | 12853759 |
| 2010 | Singapore | 12800536 |

#### Diamond League

| Year | CID |
|------|-----|
| 2025 | 13098848 |
| 2024 | 13065141 |

---

## 4. Qualification Standards

### Tokyo 2025 World Championships Entry Standards

Source: World Athletics official entry standards for the 20th World Athletics Championships (Tokyo, September 2025).

50% of athletes qualify via entry standard, 50% via WA World Rankings.

#### Men's Standards

| Event | Standard | Stored As (seconds/meters/points) |
|-------|----------|----------------------------------|
| 100m | 10.00s | 10.00 |
| 200m | 20.16s | 20.16 |
| 400m | 44.85s | 44.85 |
| 800m | 1:44.50 | 104.50 |
| 1500m | 3:33.00 | 213.00 |
| Mile | 3:50.00 | 230.00 |
| 5000m | 13:01.00 | 781.00 |
| 10000m | 27:00.00 | 1620.00 |
| Marathon | 2:06:30 | 7590.00 |
| 3000m Steeplechase | 8:15.00 | 495.00 |
| 110m Hurdles | 13.27s | 13.27 |
| 400m Hurdles | 48.50s | 48.50 |
| 20km Race Walk | 1:19:20 | 4760.00 |
| 35km Race Walk | 2:28:00 | 8880.00 |
| High Jump | 2.33m | 2.33 |
| Pole Vault | 5.82m | 5.82 |
| Long Jump | 8.27m | 8.27 |
| Triple Jump | 17.22m | 17.22 |
| Shot Put | 21.50m | 21.50 |
| Discus Throw | 67.50m | 67.50 |
| Hammer Throw | 78.20m | 78.20 |
| Javelin Throw | 85.50m | 85.50 |
| Decathlon | 8550 pts | 8550 |

#### Women's Standards

| Event | Standard | Stored As (seconds/meters/points) |
|-------|----------|----------------------------------|
| 100m | 11.07s | 11.07 |
| 200m | 22.57s | 22.57 |
| 400m | 50.75s | 50.75 |
| 800m | 1:59.00 | 119.00 |
| 1500m | 4:01.50 | 241.50 |
| Mile | 4:19.90 | 259.90 |
| 5000m | 14:50.00 | 890.00 |
| 10000m | 30:20.00 | 1820.00 |
| Marathon | 2:23:30 | 8610.00 |
| 3000m Steeplechase | 9:18.00 | 558.00 |
| 100m Hurdles | 12.73s | 12.73 |
| 400m Hurdles | 54.65s | 54.65 |
| 20km Race Walk | 1:29:00 | 5340.00 |
| 35km Race Walk | 2:48:00 | 10080.00 |
| High Jump | 1.97m | 1.97 |
| Pole Vault | 4.73m | 4.73 |
| Long Jump | 6.86m | 6.86 |
| Triple Jump | 14.55m | 14.55 |
| Shot Put | 18.80m | 18.80 |
| Discus Throw | 64.50m | 64.50 |
| Hammer Throw | 74.00m | 74.00 |
| Javelin Throw | 64.00m | 64.00 |
| Heptathlon | 6500 pts | 6500 |

### LA 2028 Olympics Entry Standards (Estimated)

Based on Paris 2024 standards with typical adjustments. Final standards TBD by World Athletics.

#### Men's Standards

| Event | Standard | Stored As |
|-------|----------|-----------|
| 100m | 10.00s | 10.00 |
| 200m | 20.16s | 20.16 |
| 400m | 44.90s | 44.90 |
| 800m | 1:43.50 | 103.50 |
| 1500m | 3:33.00 | 213.00 |
| 5000m | 13:00.00 | 780.00 |
| 10000m | 27:00.00 | 1620.00 |
| Marathon | 2:06:30 | 7590.00 |
| 3000m Steeplechase | 8:23.00 | 503.00 |
| 110m Hurdles | 13.27s | 13.27 |
| 400m Hurdles | 48.70s | 48.70 |
| 20km Race Walk | 1:19:00 | 4740.00 |
| High Jump | 2.33m | 2.33 |
| Pole Vault | 5.82m | 5.82 |
| Long Jump | 8.27m | 8.27 |
| Triple Jump | 17.22m | 17.22 |
| Shot Put | 21.35m | 21.35 |
| Discus Throw | 67.20m | 67.20 |
| Hammer Throw | 78.00m | 78.00 |
| Javelin Throw | 85.50m | 85.50 |
| Decathlon | 8460 pts | 8460 |

#### Women's Standards

| Event | Standard | Stored As |
|-------|----------|-----------|
| 100m | 11.07s | 11.07 |
| 200m | 22.57s | 22.57 |
| 400m | 50.40s | 50.40 |
| 800m | 1:58.00 | 118.00 |
| 1500m | 4:00.00 | 240.00 |
| 5000m | 14:42.00 | 882.00 |
| 10000m | 30:00.00 | 1800.00 |
| Marathon | 2:21:00 | 8460.00 |
| 3000m Steeplechase | 9:15.00 | 555.00 |
| 100m Hurdles | 12.77s | 12.77 |
| 400m Hurdles | 54.85s | 54.85 |
| 20km Race Walk | 1:28:00 | 5280.00 |
| High Jump | 1.97m | 1.97 |
| Pole Vault | 4.73m | 4.73 |
| Long Jump | 6.86m | 6.86 |
| Triple Jump | 14.55m | 14.55 |
| Shot Put | 18.80m | 18.80 |
| Discus Throw | 64.50m | 64.50 |
| Hammer Throw | 74.00m | 74.00 |
| Javelin Throw | 64.00m | 64.00 |
| Heptathlon | 6480 pts | 6480 |

### EVENT_QUOTAS (Target Field Sizes)

Qualification split: ~50% entry standard, ~50% WA World Rankings.

| Event | Total Field | Ranking Quota |
|-------|------------|---------------|
| **Sprints** | | |
| 100m | 48 | 24 |
| 200m | 48 | 24 |
| 400m | 48 | 24 |
| **Middle Distance** | | |
| 800m | 48 | 24 |
| 1500m | 45 | 22 |
| 5000m | 42 | 21 |
| 10000m | 27 | 14 |
| **Hurdles** | | |
| 100m Hurdles | 40 | 20 |
| 110m Hurdles | 40 | 20 |
| 400m Hurdles | 40 | 20 |
| **Steeplechase** | | |
| 3000m Steeplechase | 45 | 22 |
| **Road Events** | | |
| Marathon | 80 | 40 |
| 20km Race Walk | 60 | 30 |
| 35km Race Walk | 50 | 25 |
| **Jumps** | | |
| High Jump | 32 | 16 |
| Pole Vault | 32 | 16 |
| Long Jump | 32 | 16 |
| Triple Jump | 32 | 16 |
| **Throws** | | |
| Shot Put | 32 | 16 |
| Discus Throw | 32 | 16 |
| Hammer Throw | 32 | 16 |
| Javelin Throw | 32 | 16 |
| **Combined Events** | | |
| Decathlon | 24 | 12 |
| Heptathlon | 24 | 12 |
| **Relays** | | |
| 4x100m Relay | 16 teams | 2 |
| 4x400m Relay | 16 teams | 2 |
| 4x400m Mixed Relay | 16 teams | 2 |

---

## 5. Country Codes

Full mapping of World Athletics 3-letter codes to country names.

### Middle East
| Code | Country |
|------|---------|
| KSA | Saudi Arabia |
| UAE | United Arab Emirates |
| QAT | Qatar |
| BRN | Bahrain |
| KUW | Kuwait |
| OMA | Oman |
| JOR | Jordan |
| LBN | Lebanon |
| SYR | Syria |
| IRQ | Iraq |
| YEM | Yemen |
| PLE | Palestine |
| IRI | Iran |

### Africa
| Code | Country |
|------|---------|
| KEN | Kenya |
| ETH | Ethiopia |
| RSA | South Africa |
| NGR | Nigeria |
| MAR | Morocco |
| ALG | Algeria |
| TUN | Tunisia |
| EGY | Egypt |
| GHA | Ghana |
| UGA | Uganda |
| TAN | Tanzania |
| CMR | Cameroon |
| SEN | Senegal |
| CIV | Ivory Coast |
| SUD | Sudan |
| LBA | Libya |
| ERI | Eritrea |
| RWA | Rwanda |
| BDI | Burundi |
| NAM | Namibia |
| BOT | Botswana |
| ZIM | Zimbabwe |
| ZAM | Zambia |
| MOZ | Mozambique |
| ANG | Angola |
| GAB | Gabon |
| TOG | Togo |
| BEN | Benin |
| MLI | Mali |
| BUR | Burkina Faso |
| NIG | Niger |
| MAD | Madagascar |
| MRI | Mauritius |
| SEY | Seychelles |
| DJI | Djibouti |
| SOM | Somalia |
| CPV | Cape Verde |

### Europe (Key Nations)
| Code | Country |
|------|---------|
| GBR | Great Britain |
| GER | Germany |
| FRA | France |
| ITA | Italy |
| ESP | Spain |
| NED | Netherlands |
| NOR | Norway |
| SWE | Sweden |
| POL | Poland |
| TUR | Turkey |

### Americas (Key Nations)
| Code | Country |
|------|---------|
| USA | United States |
| CAN | Canada |
| JAM | Jamaica |
| CUB | Cuba |
| BRA | Brazil |
| DOM | Dominican Republic |
| BAH | Bahamas |
| TTO | Trinidad and Tobago |
| GRN | Grenada |

### Asia (KSA Rivals & Key Nations)
| Code | Country |
|------|---------|
| CHN | China |
| JPN | Japan |
| KOR | South Korea |
| IND | India |
| PAK | Pakistan |
| SRI | Sri Lanka |
| THA | Thailand |
| PHI | Philippines |
| TPE | Chinese Taipei |
| KAZ | Kazakhstan |
| UZB | Uzbekistan |
| TJK | Tajikistan |
| MGL | Mongolia |

### Oceania
| Code | Country |
|------|---------|
| AUS | Australia |
| NZL | New Zealand |

### Special Codes
| Code | Entity |
|------|--------|
| AIN | Individual Neutral Athletes |

---

## 6. Athletics Domain Knowledge

### Timing

- **FAT (Fully Automatic Timing)**: Electronic timing used at all major competitions. Accuracy to 1/100th (0.01s) for track events up to 10000m, 1/10th for road events.
- **Hand Timing**: Manual stopwatch timing. Less accurate; +0.24s is added to hand-timed 100m/200m results for equivalency with FAT. For 400m and longer, +0.14s is added.
- **Photo Finish**: Camera at the finish line provides the official FAT result.
- **Wind Reading**: Measured for 100m, 200m, 100m Hurdles, 110m Hurdles, Long Jump, Triple Jump. Legal limit is +2.0 m/s. Results with tailwind above +2.0 m/s are "wind-assisted" and do not count for records or qualification standards.
- **Wind column values**: Numeric (e.g., "2.6", "-0.3", "0.0"). The `windlegal` column indicates "Wind Legal" or "Wind Assisted".

### Result Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| DNS | Did Not Start | Athlete entered but did not start the race/attempt |
| DNF | Did Not Finish | Athlete started but did not complete the event |
| DQ | Disqualified | Athlete was disqualified (false start, lane infringement, walking violation, etc.) |
| NM | No Mark | Field event athlete had no valid attempts (all fouls) |
| NH | No Height | High Jump/Pole Vault athlete cleared no height |
| r | Retired | Athlete withdrew during event |
| "" (empty) | No result | No performance recorded |

These result codes produce `NULL` in the `result_numeric` column. Always filter them out for performance analysis.

### Competition Rounds

| Round Code | Normalized Name | Description |
|------------|----------------|-------------|
| h, h1, h2...h8, Heat, heat | Heats | First round of elimination |
| sf, Semi, semi-final | Semi Finals | Second round (typically top 24 from heats) |
| f, Final, final | Final | Championship deciding round (top 8/12) |
| q, Q, qual, Qualification | Qualification | Field event qualifying round |
| rB, r | Repechage | Second-chance round (introduced Paris 2024 for sprint events) |

**Advancement rules (typical):**
- Heats: Top 3 per heat (Q) + next fastest times (q) advance. At Paris 2024 Olympics, sprints used repechage system instead of fastest losers.
- Semi-finals: Top 2 per semi (Q) + next 2 fastest (q) advance to final.
- Finals: Top 8 positions scored. Top 3 receive medals.
- Field event qualifying: Must achieve qualifying standard or top 12 advance.

**Round normalization mapping used in database:**
- `heats`, `heat`, `h` -> `Heats`
- `semi`, `semi final`, `sf`, `semi-final` -> `Semi Finals`
- `final`, `f`, `a final`, `final a` -> `Final`
- `qualification`, `qual`, `q` -> `Qualification`
- Empty or `none` -> `Final` (assumed final for events with single round)

### Age Groups

| Category | Age Range | Notes |
|----------|-----------|-------|
| U18 | Under 18 | Youth category |
| U20 | Under 20 | Junior category (formerly World Juniors) |
| Senior | 20+ (open) | Main category for Olympics and World Championships |
| Masters | 35+ | Age-graded categories (M35, M40, M45, etc.) |

Age is determined by the athlete's age on December 31st of the competition year.

### WA Points Scale

World Athletics Points (wapoints) is a scoring system that allows comparison across events:

| Points Range | Level | Description |
|-------------|-------|-------------|
| 0-400 | Club/Recreational | Local competition level |
| 400-700 | National | Competitive at national level |
| 700-900 | National Elite | Top of national rankings |
| 900-1000 | International | Competitive at continental championships |
| 1000-1100 | International Elite | World Championship heat/semi level |
| 1100-1200 | World Class | World Championship finalist level |
| 1200-1300 | World Elite | Medal contender at World Championships/Olympics |
| 1300+ | All-Time | Historic performances, near world record |

**Usage in database**: The `wapoints` column is numeric. Useful for comparing athletes across different events (e.g., is a 10.15s 100m runner better than a 2.28m high jumper?). Higher points always = better performance regardless of event type.

### Season Calendar

| Period | Season | Key Championships |
|--------|--------|-------------------|
| January - March | Indoor Season | World Indoor Championships, Asian Indoor Championships |
| April - October | Outdoor Season | Olympics, World Championships, Asian Games, Diamond League |
| November - December | Off-season / Cross-country | |

**Key qualification windows:**
- Most events: August 1 of previous year through August 24 of championship year
- Marathon/race walk: Earlier start (November of previous year)
- Combined events (Decathlon/Heptathlon): February 25 of previous year

### Personal Best (PB) vs Season Best (SB)

- **PB (Personal Best)**: The best performance an athlete has ever achieved in their career. In the database, the `PB` column contains "PB" if that specific result is/was their personal best at time of recording.
- **SB (Season Best)**: The best performance achieved in the current calendar year (January 1 - December 31). The `SB` column contains "SB" if that result is/was their season best.
- An athlete's PB may have been set years ago; their SB shows current-year form.

### Primary Focus: Saudi Arabia (KSA)

- **Country Code**: KSA
- **Full Name**: Kingdom of Saudi Arabia
- **Key Context**: This tool is primarily built for Saudi Arabian athletics coaching and performance analysis
- **Notable Saudi athletes appear in events**: Sprints (100m, 200m, 400m), jumps (Long Jump, Triple Jump, High Jump), throws (Shot Put, Javelin), middle distance
- **Saudi Asian Records**: Mohammed Issa holds the Asian Long Jump record (8.47m); Sultan Al-Dawoodi holds the Asian Shot Put record (21.49m)

### Key Regional Championships

| Championship | Frequency | Importance for KSA |
|-------------|-----------|-------------------|
| Asian Games | Every 4 years | Major multi-sport event; primary regional target |
| Asian Athletics Championships | Every 2 years | Continental athletics-specific championship |
| Arab Championships | Irregular | Arab nations only |
| Islamic Solidarity Games | Every 4 years | OIC member nations |
| Gulf Championships (GCC) | Irregular | GCC nations only |
| Diamond League | Annual series | Elite invitational circuit (select KSA athletes) |

### Athlete Deduplication Rules

The system handles common data quality issues:
1. **ID normalization**: `147939`, `147939.0`, `'147939.0'` all normalize to `'147939'`
2. **Arabic name normalization**: `Al-Jadani`, `Al Jadani`, `al-jadani`, `AlJadani` all normalize to `al jadani`
3. **Manual ID mappings**: Known duplicate IDs are mapped to canonical IDs (e.g., athlete ID `652065` maps to `147939` for Al Jadani)
4. **Name matching**: Uses normalized name keys (`firstname|lastname`) to detect duplicates with different IDs
5. **Canonical ID selection**: When multiple IDs exist for the same athlete, the lowest numeric ID is chosen as canonical

### Performance Projection Methodology

The system uses statistical projections for athlete form estimation:

**Weighted Average with Recency Bias:**
- Most recent performance: weight 1.00
- 2nd most recent: weight 0.85
- 3rd most recent: weight 0.72
- 4th most recent: weight 0.61
- 5th most recent: weight 0.52

**Confidence Range:** Plus/minus 1 standard deviation (68% probability the actual performance falls within this range).

**Championship Pressure Adjustment:** +0.5% added to time events for major championships (accounts for racing pressure, multiple rounds, and tactical considerations). For distance/points events, performances are reduced by 0.5%.

**Trend Detection:** Compares average of 2 most recent vs 2 oldest performances:
- Improving: >2% improvement
- Declining: >2% decline
- Stable: Within 2%

**Advancement Probability:** Uses logistic function comparing projected performance to historical round cutoffs from the last 3-5 championship editions.

### Historical Benchmark Methodology

Benchmarks represent what it takes to reach each stage of a championship:

| Benchmark | Definition | Data Source |
|-----------|-----------|-------------|
| Medal Line | Average performance of gold, silver, bronze medalists | Last 3-5 editions of championship |
| Final Line | Average of all finalists (top 8) | Last 3-5 editions |
| Semi-Final Line | Typical qualifying performance from semis | Estimated from advancing athletes |
| Heat Survival | Minimum performance to advance from heats | Historical heat qualifying marks |

**Data sources for benchmarks:**
- Olympics: 2024, 2021, 2016, 2012, 2008 (CIDs: 13079218, 12992925, 12877460, 12825110, 12042259)
- World Championships: 2023, 2022, 2019, 2017, 2013 (CIDs: 13046619, 13002354, 12935526, 12898707, 12844203)
- Asian Games: 2023, 2018, 2014 (CIDs: 13048549, 12911586, 12854365)

**Default benchmarks (when historical data is insufficient):**

Men's defaults (selected events):

| Event | Medal | Final | Semi | Heat |
|-------|-------|-------|------|------|
| 100m | 9.85 | 10.02 | 10.12 | 10.25 |
| 200m | 19.85 | 20.15 | 20.35 | 20.55 |
| 400m | 44.20 | 44.60 | 45.10 | 45.50 |
| 800m | 1:43.50 | 1:44.50 | 1:46.00 | 1:47.50 |
| 1500m | 3:32.00 | 3:35.00 | 3:38.00 | 3:42.00 |
| 110m Hurdles | 13.05 | 13.25 | 13.45 | 13.65 |
| 400m Hurdles | 47.50 | 48.20 | 49.00 | 49.80 |
| High Jump | 2.35 | 2.28 | - | 2.25 |
| Long Jump | 8.35 | 8.10 | - | 8.00 |
| Shot Put | 22.50 | 21.50 | - | 20.80 |
| Javelin Throw | 88.00 | 84.00 | - | 82.00 |

Women's defaults (selected events):

| Event | Medal | Final | Semi | Heat |
|-------|-------|-------|------|------|
| 100m | 10.85 | 11.02 | 11.15 | 11.30 |
| 200m | 22.00 | 22.35 | 22.60 | 22.90 |
| 400m | 49.50 | 50.20 | 51.00 | 51.80 |
| 800m | 1:57.00 | 1:59.00 | 2:01.00 | 2:03.00 |
| 100m Hurdles | 12.45 | 12.65 | 12.85 | 13.05 |
| 400m Hurdles | 53.00 | 54.00 | 55.00 | 56.00 |
| High Jump | 2.00 | 1.94 | - | 1.90 |
| Long Jump | 7.00 | 6.75 | - | 6.60 |

Note: "-" means that round does not apply for field events (no semi-finals in field events).

---

## 7. SQL Query Guidelines

### Database Access

- The table is accessed via DuckDB as `athletics_data`
- All queries run against the single table `athletics_data`
- The database contains pre-computed columns (`result_numeric`, `year`, `round_normalized`) to avoid runtime parsing

### Column Usage Rules

| Column | Type | Notes |
|--------|------|-------|
| `Athlete_CountryCode` | TEXT | 3-letter codes: `'KSA'`, `'USA'`, `'QAT'` |
| `Gender` | TEXT | Always `'Men'` or `'Women'` (NOT 'M'/'F') |
| `Event` | TEXT | Exact match: `'100m'`, `'Long Jump'`, `'4x400m Relay'` |
| `Competition_ID` | TEXT | String format: `'13079218'` |
| `Start_Date` | TEXT | String format `'YYYY-MM-DD'` |
| `result_numeric` | REAL | Pre-computed numeric. NULL for DNS/DNF/DQ/NM |
| `wapoints` | REAL | Numeric. Can use AVG(), MAX(), MIN() |
| `Round` | TEXT | Readable: `'Final'`, `'Heat 1'`, `'Semi 2'` |
| `round_normalized` | TEXT | Standardized: `'Final'`, `'Semi Finals'`, `'Heats'` |
| `year` | INTEGER | Pre-computed from Start_Date |
| `Position` | TEXT | Finishing position as string (cast to INT for sorting) |
| `PB` | TEXT | Contains `'PB'` or empty |
| `SB` | TEXT | Contains `'SB'` or empty |
| `Athlete_Name` | TEXT | Full name (firstname + lastname) |
| `firstname` | TEXT | First name only |
| `lastname` | TEXT | Last name only |
| `Athlete_ID` | TEXT | Unique athlete identifier |
| `Competition` | TEXT | Full competition name |
| `Result` | TEXT | Raw result string |

### Important Query Patterns

1. **Always use single quotes** for string values: `WHERE Athlete_CountryCode = 'KSA'`
2. **Time comparisons**: Lower `result_numeric` = faster = better. Use `MIN()` for best time, `ORDER BY result_numeric ASC` for fastest first.
3. **Distance comparisons**: Higher `result_numeric` = further = better. Use `MAX()` for best distance, `ORDER BY result_numeric DESC` for longest first.
4. **Filter NULL results**: Always add `AND result_numeric IS NOT NULL` to exclude DNS/DNF/DQ/NM.
5. **Use LIKE for partial event matching**: `WHERE Event LIKE '%Hurdles%'` matches all hurdle variants.
6. **Date filtering**: `WHERE Start_Date >= '2024-01-01'` or `WHERE year >= 2024`.
7. **Round filtering**: Use `round_normalized` for clean filtering: `WHERE round_normalized = 'Final'`.
8. **Athlete name**: Use `Athlete_Name` directly (already combined). Or `firstname`, `lastname` separately.
9. **WA Points aggregation**: `AVG(wapoints)`, `MAX(wapoints)` work directly on the numeric column.
10. **Cast position for sorting**: `CAST(Position AS INTEGER)` when ordering by finish place.

### Performance Time Storage

All time-based results are stored in **seconds** in `result_numeric`:
- 10.15 seconds = `10.15`
- 1:44.50 (1 min 44.50 sec) = `104.50`
- 2:06:30 (2 hr 6 min 30 sec) = `7590.00`

To display times from `result_numeric`:
- If value < 60: display as `SS.ss` (e.g., 10.15)
- If 60 <= value < 3600: display as `M:SS.ss` (e.g., 1:44.50)
- If value >= 3600: display as `H:MM:SS.ss` (e.g., 2:06:30.00)

---

## 8. Example Queries

### Finding Athlete Results

**Q: Show me all results for Mohammed Al-Jadani**
```sql
SELECT Athlete_Name, Event, Result, result_numeric,
       Competition, Start_Date, wapoints
FROM athletics_data
WHERE Athlete_Name LIKE '%Mohammed%Jadani%'
  AND result_numeric IS NOT NULL
ORDER BY Start_Date DESC
```

**Q: What are the best 100m times by KSA athletes?**
```sql
SELECT Athlete_Name, Result, result_numeric, Competition,
       Start_Date, wind, wapoints
FROM athletics_data
WHERE Athlete_CountryCode = 'KSA'
  AND Event = '100m'
  AND Gender = 'Men'
  AND result_numeric IS NOT NULL
ORDER BY result_numeric ASC
LIMIT 20
```

### Comparing Athletes

**Q: Compare the top 400m Hurdles athletes from Qatar and Saudi Arabia**
```sql
SELECT Athlete_CountryCode, Athlete_Name,
       MIN(result_numeric) AS personal_best,
       AVG(result_numeric) AS average_performance,
       MAX(wapoints) AS best_wapoints,
       COUNT(*) AS total_races
FROM athletics_data
WHERE Event = '400m Hurdles'
  AND Gender = 'Men'
  AND Athlete_CountryCode IN ('KSA', 'QAT')
  AND result_numeric IS NOT NULL
GROUP BY Athlete_CountryCode, Athlete_ID, Athlete_Name
ORDER BY personal_best ASC
```

**Q: Head-to-head: Two specific athletes in the same competitions**
```sql
SELECT a.Competition, a.Start_Date,
       a.Athlete_Name AS athlete_a,
       a.Result AS result_a, a.result_numeric AS numeric_a,
       b.Athlete_Name AS athlete_b,
       b.Result AS result_b, b.result_numeric AS numeric_b
FROM athletics_data a
JOIN athletics_data b
  ON a.Competition_ID = b.Competition_ID
  AND a.Event = b.Event
  AND a.Round = b.Round
WHERE a.Athlete_ID = '147939'
  AND b.Athlete_ID = '652065'
  AND a.result_numeric IS NOT NULL
  AND b.result_numeric IS NOT NULL
ORDER BY a.Start_Date DESC
```

### Championship Analysis

**Q: Who were the 100m finalists at the Paris 2024 Olympics?**
```sql
SELECT CAST(Position AS INTEGER) AS place,
       Athlete_Name, Athlete_CountryCode, Result, result_numeric, wapoints
FROM athletics_data
WHERE Competition_ID = '13079218'
  AND Event = '100m'
  AND Gender = 'Men'
  AND round_normalized = 'Final'
  AND result_numeric IS NOT NULL
ORDER BY CAST(Position AS INTEGER) ASC
```

**Q: How have 400m medal-winning times trended at World Championships?**
```sql
SELECT Competition, year,
       MIN(result_numeric) AS gold_time,
       AVG(result_numeric) AS avg_medal_time
FROM athletics_data
WHERE Competition_ID IN ('13046619','13002354','12935526','12898707','12844203',
                        '12814135','12789100','10626603','8906660','7993620')
  AND Event = '400m'
  AND Gender = 'Men'
  AND round_normalized = 'Final'
  AND CAST(Position AS INTEGER) <= 3
  AND result_numeric IS NOT NULL
GROUP BY Competition_ID, Competition, year
ORDER BY year ASC
```

### Rankings and Personal Bests

**Q: What are the all-time best performances in the men's Long Jump?**
```sql
SELECT Athlete_Name, Athlete_CountryCode,
       MAX(result_numeric) AS pb,
       MAX(wapoints) AS best_points
FROM athletics_data
WHERE Event = 'Long Jump'
  AND Gender = 'Men'
  AND result_numeric IS NOT NULL
GROUP BY Athlete_ID, Athlete_Name, Athlete_CountryCode
ORDER BY pb DESC
LIMIT 50
```

**Q: Which KSA athletes achieved a personal best (PB) in 2024?**
```sql
SELECT Athlete_Name, Event, Result, result_numeric, wapoints,
       Competition, Start_Date
FROM athletics_data
WHERE Athlete_CountryCode = 'KSA'
  AND year = 2024
  AND PB = 'PB'
  AND result_numeric IS NOT NULL
ORDER BY wapoints DESC
```

### Event Analysis

**Q: What performances are needed to make the 200m final at World Championships?**
```sql
SELECT Competition, year, round_normalized,
       MIN(result_numeric) AS fastest,
       AVG(result_numeric) AS average,
       MAX(result_numeric) AS slowest_qualifier
FROM athletics_data
WHERE Competition_ID IN ('13046619','13002354','12935526','12898707','12844203')
  AND Event = '200m'
  AND Gender = 'Men'
  AND result_numeric IS NOT NULL
GROUP BY Competition_ID, Competition, year, round_normalized
ORDER BY year DESC,
  CASE round_normalized
    WHEN 'Final' THEN 1
    WHEN 'Semi Finals' THEN 2
    WHEN 'Heats' THEN 3
    ELSE 4
  END
```

**Q: Distribution of WA Points in the men's Shot Put across all competitions**
```sql
SELECT
  CASE
    WHEN wapoints >= 1200 THEN 'World Elite (1200+)'
    WHEN wapoints >= 1000 THEN 'World Class (1000-1199)'
    WHEN wapoints >= 800 THEN 'International (800-999)'
    WHEN wapoints >= 600 THEN 'National Elite (600-799)'
    ELSE 'Club Level (<600)'
  END AS level,
  COUNT(*) AS count,
  ROUND(AVG(result_numeric), 2) AS avg_distance
FROM athletics_data
WHERE Event = 'Shot Put'
  AND Gender = 'Men'
  AND wapoints IS NOT NULL
  AND wapoints > 0
  AND result_numeric IS NOT NULL
GROUP BY level
ORDER BY MIN(wapoints) DESC
```

### KSA-Specific Queries

**Q: How many KSA athletes competed at each Asian Games?**
```sql
SELECT Competition, Start_Date,
       COUNT(DISTINCT Athlete_ID) AS ksa_athletes,
       COUNT(DISTINCT Event) AS events_entered,
       COUNT(*) AS total_results
FROM athletics_data
WHERE Athlete_CountryCode = 'KSA'
  AND Competition_ID IN ('13048549', '12911586', '12854365')
GROUP BY Competition_ID, Competition, Start_Date
ORDER BY Start_Date DESC
```

**Q: KSA season best performances for 2025**
```sql
SELECT Event, Gender,
       Athlete_Name,
       MIN(CASE WHEN Event IN ('High Jump','Pole Vault','Long Jump','Triple Jump',
                                     'Shot Put','Discus Throw','Hammer Throw','Javelin Throw',
                                     'Decathlon','Heptathlon')
                THEN -result_numeric ELSE result_numeric END) AS best_numeric,
       Result AS best_performance,
       wapoints, Competition
FROM athletics_data
WHERE Athlete_CountryCode = 'KSA'
  AND year = 2025
  AND result_numeric IS NOT NULL
GROUP BY Event, Gender, Athlete_ID, Athlete_Name
ORDER BY Event, Gender, best_numeric ASC
```

**Q: KSA athletes who have achieved Tokyo 2025 World Championship entry standards**
```sql
-- Example for 100m Men (standard: 10.00s)
SELECT Athlete_Name,
       MIN(result_numeric) AS personal_best,
       MAX(wapoints) AS best_points
FROM athletics_data
WHERE Athlete_CountryCode = 'KSA'
  AND Event = '100m'
  AND Gender = 'Men'
  AND result_numeric IS NOT NULL
  AND result_numeric <= 10.00
  AND Start_Date >= '2024-08-01'
GROUP BY Athlete_ID, Athlete_Name
ORDER BY personal_best ASC
```

**Q: All KSA results at any major championship, with medal positions highlighted**
```sql
SELECT Competition, year, Event,
       Athlete_Name,
       round_normalized, CAST(Position AS INTEGER) AS place,
       Result, result_numeric, wapoints,
       CASE
         WHEN round_normalized = 'Final' AND CAST(Position AS INTEGER) <= 3 THEN 'MEDAL'
         WHEN round_normalized = 'Final' THEN 'Finalist'
         WHEN round_normalized = 'Semi Finals' THEN 'Semi-Finalist'
         ELSE 'Participated'
       END AS achievement
FROM athletics_data
WHERE Athlete_CountryCode = 'KSA'
  AND Competition_ID IN (
    '13079218','12992925','12877460','12825110','12042259',
    '13112510','13046619','13002354','12935526','12898707',
    '13048549','12911586','12854365',
    '13105634','13045167','12927085'
  )
  AND result_numeric IS NOT NULL
ORDER BY year DESC, Event,
  CASE round_normalized
    WHEN 'Final' THEN 1
    WHEN 'Semi Finals' THEN 2
    WHEN 'Heats' THEN 3
    ELSE 4
  END,
  CAST(Position AS INTEGER) ASC
```

**Q: Year-over-year improvement for a KSA athlete**
```sql
SELECT year, Event,
       MIN(result_numeric) AS season_best,
       AVG(result_numeric) AS season_average,
       MAX(wapoints) AS best_wapoints,
       COUNT(*) AS races
FROM athletics_data
WHERE Athlete_ID = '147939'
  AND Event = '400m'
  AND result_numeric IS NOT NULL
GROUP BY year, Event
ORDER BY year ASC
```

---

## 9. Records Reference

### Selected Asian Records (Men) - Key for KSA Rival Context

| Event | Record | Athlete | Country |
|-------|--------|---------|---------|
| 100m | 9.83 | Su Bingtian | CHN |
| 200m | 19.88 | Xie Zhenye | CHN |
| 400m | 44.65 | Femi Ogunode | QAT |
| 400m Hurdles | 47.79 | Abderrahman Samba | QAT |
| High Jump | 2.39 | Mutaz Essa Barshim | QAT |
| Pole Vault | 5.92 | EJ Obiena | PHI |
| Long Jump | 8.47 | Mohammed Issa | KSA |
| Shot Put | 21.49 | Sultan Al-Dawoodi | KSA |
| Discus Throw | 69.32 | Ehsan Hadadi | IRI |
| Javelin Throw | 92.97 | Neeraj Chopra | IND |
| Hammer Throw | 81.22 | Koji Murofushi | JPN |

---

## 10. Coaching-Specific Query Patterns

These examples cover the most common coaching questions about KSA athletes preparing for major championships.

### Gap-to-Standard Analysis

**Q: How far are KSA 400m athletes from the World Championship standard?**
```sql
SELECT Athlete_Name,
       MIN(result_numeric) AS personal_best,
       ROUND(MIN(result_numeric) - 44.85, 2) AS gap_to_tokyo_2025,
       ROUND(MIN(result_numeric) - 44.90, 2) AS gap_to_la_2028,
       MAX(wapoints) AS best_wapoints,
       COUNT(*) AS races
FROM athletics_data
WHERE Athlete_CountryCode = 'KSA'
  AND Event = '400m'
  AND Gender = 'Men'
  AND result_numeric IS NOT NULL
  AND year >= 2023
GROUP BY Athlete_ID, Athlete_Name
ORDER BY personal_best ASC
```
Note: For time events, negative gap = already under the standard (qualified). For field events, reverse the comparison (PB - standard; positive = already above standard).

**Q: Which KSA athletes are closest to qualifying for Tokyo 2025?**
```sql
SELECT Athlete_Name, Event,
       MIN(result_numeric) AS personal_best,
       CASE
         WHEN Event IN ('100m','200m','400m','800m','1500m','5000m','10000m',
                        '110m Hurdles','100m Hurdles','400m Hurdles',
                        '3000m Steeplechase','Marathon','20km Race Walk','35km Race Walk')
         THEN 'time'
         ELSE 'distance'
       END AS event_type,
       MAX(wapoints) AS best_wapoints
FROM athletics_data
WHERE Athlete_CountryCode = 'KSA'
  AND result_numeric IS NOT NULL
  AND year >= 2024
GROUP BY Athlete_ID, Athlete_Name, Event
ORDER BY best_wapoints DESC
LIMIT 20
```

### Rival / Competitor Analysis

**Q: Who are KSA's closest rivals in the Long Jump at Asian level?**
```sql
SELECT Athlete_Name, Athlete_CountryCode,
       MAX(result_numeric) AS personal_best,
       MAX(CASE WHEN year = 2025 THEN result_numeric END) AS season_best_2025,
       MAX(CASE WHEN year = 2024 THEN result_numeric END) AS season_best_2024,
       MAX(wapoints) AS best_wapoints,
       COUNT(*) AS total_competitions
FROM athletics_data
WHERE Event = 'Long Jump'
  AND Gender = 'Men'
  AND result_numeric IS NOT NULL
  AND year >= 2023
  AND Athlete_CountryCode IN ('KSA','JPN','CHN','IND','QAT','BRN','IRI','KOR','TPE','THA','KAZ','UZB','PHI')
GROUP BY Athlete_ID, Athlete_Name, Athlete_CountryCode
ORDER BY personal_best DESC
LIMIT 20
```

**Q: Head-to-head: KSA vs Qatar in sprint events at recent Asian Championships**
```sql
SELECT Event, Athlete_Name, Athlete_CountryCode,
       Result, result_numeric, round_normalized,
       CAST(Position AS INTEGER) AS place,
       Competition, year
FROM athletics_data
WHERE Competition_ID IN ('13105634','13045167','12927085','12897142')
  AND Athlete_CountryCode IN ('KSA', 'QAT')
  AND Event IN ('100m', '200m', '400m')
  AND Gender = 'Men'
  AND result_numeric IS NOT NULL
ORDER BY Event, year DESC, round_normalized,
  CAST(Position AS INTEGER) ASC
```

**Q: Who beat KSA athletes at the 2023 Asian Games?**
```sql
SELECT a.Event, a.Athlete_Name AS ksa_athlete, a.Result AS ksa_result,
       a.result_numeric AS ksa_numeric,
       b.Athlete_Name AS rival, b.Athlete_CountryCode AS rival_country,
       b.Result AS rival_result, b.result_numeric AS rival_numeric,
       b.round_normalized, CAST(b.Position AS INTEGER) AS rival_place
FROM athletics_data a
JOIN athletics_data b
  ON a.Competition_ID = b.Competition_ID
  AND a.Event = b.Event
  AND a.round_normalized = b.round_normalized
  AND a.Gender = b.Gender
WHERE a.Athlete_CountryCode = 'KSA'
  AND b.Athlete_CountryCode != 'KSA'
  AND a.Competition_ID = '13048549'
  AND a.result_numeric IS NOT NULL
  AND b.result_numeric IS NOT NULL
  AND CAST(b.Position AS INTEGER) < CAST(a.Position AS INTEGER)
ORDER BY a.Event, a.round_normalized, CAST(b.Position AS INTEGER)
```

### Championship Readiness

**Q: Show KSA medal chances at the next Asian Games based on current form**
```sql
WITH ksa_bests AS (
  SELECT Athlete_Name, Event, Gender,
         MIN(CASE WHEN Event IN ('High Jump','Pole Vault','Long Jump','Triple Jump',
                                  'Shot Put','Discus Throw','Hammer Throw','Javelin Throw',
                                  'Decathlon','Heptathlon')
              THEN -result_numeric ELSE result_numeric END) AS best_sort,
         MIN(result_numeric) AS best_time,
         MAX(result_numeric) AS best_distance,
         MAX(wapoints) AS best_wapoints
  FROM athletics_data
  WHERE Athlete_CountryCode = 'KSA'
    AND result_numeric IS NOT NULL
    AND year >= 2024
  GROUP BY Athlete_ID, Athlete_Name, Event, Gender
),
asian_games_medals AS (
  SELECT Event, Gender,
         AVG(CASE WHEN CAST(Position AS INTEGER) <= 3 THEN result_numeric END) AS avg_medal_perf,
         MIN(CASE WHEN CAST(Position AS INTEGER) = 1 THEN result_numeric END) AS gold_perf
  FROM athletics_data
  WHERE Competition_ID = '13048549'
    AND round_normalized = 'Final'
    AND result_numeric IS NOT NULL
  GROUP BY Event, Gender
)
SELECT k.Athlete_Name, k.Event, k.Gender,
       k.best_wapoints,
       m.avg_medal_perf AS asian_games_2023_medal_avg
FROM ksa_bests k
LEFT JOIN asian_games_medals m ON k.Event = m.Event AND k.Gender = m.Gender
WHERE k.best_wapoints > 800
ORDER BY k.best_wapoints DESC
```

**Q: KSA results across all Asian Games editions**
```sql
SELECT Competition, year, Event,
       Athlete_Name, round_normalized,
       CAST(Position AS INTEGER) AS place,
       Result, result_numeric, wapoints,
       CASE
         WHEN round_normalized = 'Final' AND CAST(Position AS INTEGER) = 1 THEN 'GOLD'
         WHEN round_normalized = 'Final' AND CAST(Position AS INTEGER) = 2 THEN 'SILVER'
         WHEN round_normalized = 'Final' AND CAST(Position AS INTEGER) = 3 THEN 'BRONZE'
         WHEN round_normalized = 'Final' THEN 'Finalist'
         ELSE 'Participated'
       END AS achievement
FROM athletics_data
WHERE Athlete_CountryCode = 'KSA'
  AND Competition_ID IN ('13048549', '12911586', '12854365')
  AND result_numeric IS NOT NULL
ORDER BY year DESC, Event,
  CASE round_normalized WHEN 'Final' THEN 1 WHEN 'Semi Finals' THEN 2 ELSE 3 END,
  CAST(Position AS INTEGER)
```

### Performance Trends & Form

**Q: Is Mohammed Al-Yami improving in the 100m this season?**
```sql
SELECT Start_Date, Competition, Result, result_numeric,
       wapoints, Round, wind
FROM athletics_data
WHERE Athlete_Name LIKE '%Yami%'
  AND Event = '100m'
  AND result_numeric IS NOT NULL
ORDER BY Start_Date DESC
LIMIT 20
```

**Q: KSA athletes with improving form (multiple recent PBs)**
```sql
SELECT Athlete_Name, Event,
       COUNT(CASE WHEN PB = 'PB' AND year >= 2024 THEN 1 END) AS recent_pbs,
       COUNT(CASE WHEN SB = 'SB' AND year = 2025 THEN 1 END) AS season_bests_2025,
       MAX(wapoints) AS peak_wapoints,
       COUNT(*) AS total_results
FROM athletics_data
WHERE Athlete_CountryCode = 'KSA'
  AND result_numeric IS NOT NULL
  AND year >= 2023
GROUP BY Athlete_ID, Athlete_Name, Event
HAVING COUNT(*) >= 3
ORDER BY recent_pbs DESC, peak_wapoints DESC
```

### Asian Regional Context

**Key Asian Rivals by Event (typical countries to compare against):**

| Event Group | Main Rival Countries |
|-------------|---------------------|
| Sprints (100m, 200m) | JPN, CHN, THA, IND, QAT |
| 400m / 400mH | QAT, BRN, IND, JPN, SRI |
| 800m / 1500m | BRN, IND, QAT, JPN |
| Long Distance | BRN, JPN, CHN, IND |
| Long Jump | JPN, CHN, IND, TPE |
| Triple Jump | CHN, JPN, IND, KAZ |
| High Jump | QAT, KOR, JPN, CHN, SYR |
| Shot Put | IND, CHN, JPN, IRI |
| Discus / Hammer | IRI, CHN, JPN, IND |
| Javelin | IND, JPN, CHN, TPE, PAK |

**Next Major Championships:**
- **Nagoya 2026 Asian Games** - Primary target for KSA squad
- **Tokyo 2025 World Championships** (Sep 2025) - CID: 13112510
- **LA 2028 Olympics** - Long-term target

### Coaching-Specific Standard References

When a coach asks "how far is [athlete] from the standard", calculate:
- **For time events:** `athlete_PB - standard` (negative = already qualified)
- **For field events:** `standard - athlete_PB` (negative = already qualified)
- **Always show gap in the original unit** (seconds for time, meters for distance)
- **Include WA Points comparison** to give cross-event context
- **Show trend** - is the athlete improving toward the standard?

When a coach asks about "rivals" or "competitors":
- Focus on athletes from the same continent (Asia) first
- Show the gap between KSA athlete's PB and the rival's PB
- Include recent form (2024-2025 results)
- Note which competitions they've faced each other in

---

## 11. KSA Athlete Profiles & Championship Targets (2025-2028)

This section contains verified performance data for KSA's key athletes. Use this to give accurate, specific coaching answers.

### Nagoya 2026 Asian Games - KSA Medal Contenders

**GOLD MEDAL FAVOURITES (ranked #1 in Asia 2024-25):**

| Event | Athlete | PB | 2025 SB | WA Pts | Asian Rank | Gap to AG2023 Gold |
|-------|---------|-----|---------|--------|------------|-------------------|
| 100m (M) | Nasser Mohamed Abdo | 9.80 | 9.80 | 1193 | #1 | +0.17 ahead of 9.97 |
| 800m (M) | Albaraa Alqarni | 1:35.49 | 1:35.49 | 1312 | #1 | Dominant, 9s clear |
| Shot Put (M) | Mohamed Daouda Tolo | 21.80 | 21.80 | 1228 | #1 | +1.44 ahead of 20.36 |

**MEDAL CONTENDERS (ranked #2-4 in Asia 2024-25):**

| Event | Athlete | PB | 2025 SB | WA Pts | Asian Rank | Gap to AG2023 Medal |
|-------|---------|-----|---------|--------|------------|-------------------|
| 200m (M) | Abdulaziz Abdou Atafi | 20.14 | 20.14 | 1198 | #2 | +0.46 ahead of bronze 20.60 |
| Triple Jump (M) | Sami Bakhit | 16.98 | 16.98 | 1162 | #3 | +0.30 ahead of bronze 16.68 |
| Pole Vault (M) | Hussain Asim Al-Hizam | 5.72 | 5.72 | 1190 | #4 | +0.07 ahead of bronze 5.65 |
| 1500m (M) | Fahad Mohamed Al-Subaie | 3:41.73 | 3:41.73 | 1082 | #2 | In contention for medal |
| Hammer Throw (M) | Mohammed Al-Dubaisi | 70.77 | 70.40 | 1044 | #4 | Near bronze line 70.79 |

**FINALISTS / TOP 8 POTENTIAL:**

| Event | Athlete | PB | WA Pts | Asian Rank | Notes |
|-------|---------|-----|--------|------------|-------|
| 400m (M) | Mazen Al-Yassin | 45.36 | 1155 | #5 | Won AG2023 gold (45.55) - defending |
| 400m (M) | Ibrahim Futayni | 46.93 | 1020 | Top 10 | Improving rapidly in 2025 |
| 100m (M) | Abdullah Abkar Mohammed | 10.13 | 1162 | Top 5 | AG2023 200m silver |
| 10,000m (M) | Tariq Ahmed Al-Amri | 28:20.56 | 1023 | #3 | AG2023 6th place finisher |
| 5000m (M) | Tariq Ahmed Al-Amri | 13:47.31 | 987 | #10 | AG2023 7th place finisher |
| 3000m SC (M) | Khalid Hazazi | 8:41.17 | 934 | #8 | Improving |
| 110m Hurdles (M) | Ali Baqer Al Jumah | 13.78 | 1062 | Top 5 | New in 2025, fast progression |
| Javelin Throw (M) | Ali Essa Abdelghani | 73.45 | 942 | Top 8 | AG2023 7th |
| Decathlon (M) | Beedh Ali Hassan | 7163 | 889 | #6 | Developing |

### Asian Games 2023 Medal Lines (Benchmark for Nagoya 2026)

**Men's Key Events:**

| Event | Gold | Silver | Bronze | 8th Place | Gold Athlete | Country |
|-------|------|--------|--------|-----------|--------------|---------|
| 100m | 9.97 | 10.02 | 10.11 | - | - | CHN |
| 200m | 20.60 | 20.63 | 20.74 | 21.07 | Koki Ueyama | JPN |
| 400m | 45.55 | - | 45.65 | 46.48 | Youssef Al-Masrahi | **KSA** |
| 800m | 1:48.05 | 1:48.43 | 1:48.51 | - | Essa Alis Kzwani | **KSA** |
| 1500m | 3:38.94 | 3:39.74 | 3:40.55 | 3:44.71 | Ajay Kumar Saroj | IND |
| 110mH | 13.41 | - | 13.50 | 13.89 | Shunya Takayama | JPN |
| 400mH | 48.04 | 48.52 | 49.16 | - | Abderrahmane Samba | QAT |
| 3000m SC | 8:19.50 | 8:23.75 | 8:26.47 | 8:54.34 | Avinash Sable | IND |
| High Jump | 2.35 | 2.33 | 2.29 | - | Mutaz Essa Barshim | QAT |
| Pole Vault | 5.90 | 5.65 | 5.65 | 5.15 | Ernest John Obiena | PHI |
| Long Jump | 8.22 | 8.19 | 8.10 | 7.76 | - | CHN |
| Triple Jump | 17.13 | 16.93 | 16.68 | 16.00 | - | CHN |
| Shot Put | 20.36 | 20.18 | 19.97 | 18.62 | Tajinderpal Singh | IND |
| Discus Throw | 62.04 | 61.82 | 61.19 | 54.65 | Hossein Rasouli | IRI |
| Hammer Throw | 72.97 | 72.42 | 70.79 | 67.57 | - | CHN |
| Javelin Throw | 88.88 | 87.54 | 82.68 | 71.41 | Neeraj Chopra | IND |

### Tokyo 2025 World Championship Standards vs KSA PBs

| Event | Tokyo 2025 Standard | LA 2028 Standard | Best KSA Athlete | KSA PB | Gap to Tokyo | Status |
|-------|---------------------|------------------|------------------|--------|-------------|--------|
| 100m (M) | 10.00 | 10.00 | Nasser Mohamed Abdo | 9.80 | -0.20 | QUALIFIED |
| 200m (M) | 20.16 | 20.16 | Abdulaziz Abdou Atafi | 20.14 | -0.02 | QUALIFIED |
| 400m (M) | 44.85 | 44.90 | Mazen Al-Yassin | 45.36 | +0.51 | Close |
| 800m (M) | 1:44.50 | 1:43.50 | Albaraa Alqarni | 1:35.49 | -9.01 | QUALIFIED |
| 1500m (M) | 3:33.00 | 3:33.00 | Fahad Al-Subaie | 3:41.73 | +8.73 | Work needed |
| 110mH (M) | 13.27 | 13.27 | Ali Baqer Al Jumah | 13.78 | +0.51 | Developing |
| 400mH (M) | 48.50 | 48.70 | - | - | - | No KSA entry |
| 3000m SC (M) | 8:15.00 | 8:23.00 | Khalid Hazazi | 8:41.17 | +26.17 | Long-term |
| Pole Vault (M) | 5.82 | 5.82 | Hussain Al-Hizam | 5.72 | +0.10 | Very close |
| Long Jump (M) | 8.27 | 8.27 | - | 7.46 | +0.81 | Work needed |
| Triple Jump (M) | 17.22 | 17.22 | Sami Bakhit | 16.98 | +0.24 | Close |
| Shot Put (M) | 21.50 | 21.35 | Mohamed Daouda Tolo | 21.80 | -0.30 | QUALIFIED |
| Hammer Throw (M) | 78.50 | 78.50 | Mohammed Al-Dubaisi | 70.77 | +7.73 | Long-term |
| Javelin Throw (M) | 85.50 | 85.50 | Ali Abdelghani | 73.45 | +12.05 | Long-term |

**KSA Athletes Currently Qualified for WC/Olympics (PB under entry standard):**
- Nasser Mohamed Abdo - 100m (9.80 vs 10.00 standard)
- Abdulaziz Abdou Atafi - 200m (20.14 vs 20.16 standard)
- Albaraa Alqarni - 800m (1:35.49 vs 1:44.50 standard)
- Mohamed Daouda Tolo - Shot Put (21.80 vs 21.50 standard)

**KSA Athletes Close to Qualifying (within 5%):**
- Hussain Al-Hizam - Pole Vault (5.72 vs 5.82, gap: 0.10m)
- Sami Bakhit - Triple Jump (16.98 vs 17.22, gap: 0.24m)
- Mazen Al-Yassin - 400m (45.36 vs 44.85, gap: 0.51s)

### KSA Championship Medal History (Recent)

**Asian Games 2023 Hangzhou - KSA Medals:**
- GOLD: Youssef Al-Masrahi (400m, 45.55)
- GOLD: Essa Alis Kzwani (800m, 1:48.05)
- SILVER: Mohamed Daouda Tolo (Shot Put, 20.18)
- SILVER: Abdullah Abkar Mohammed (200m, 20.63)
- BRONZE: Hussain Asim Al-Hizam (Pole Vault, 5.65)

**2025 Asian Athletics Championships Gumi - KSA Medals:**
- SILVER: Abdulaziz Abdou Atafi (200m, 20.31)
- BRONZE: Abdullah Abkar Mohammed (100m, 10.30)
- BRONZE: Mohamed Daouda Tolo (Shot Put, 19.92)

**2025 Tokyo World Championships - KSA Representatives:**
- Abdulaziz Atafi (200m - heat, 20.66)
- Hussain Al-Hizam (Pole Vault)
- Mohamed Daouda Tolo (Shot Put)
- Sami Bakhit (Triple Jump)
- Lujain Ibrahim Alhumaid (100m Women)

**2024 Paris Olympics - KSA Representative:**
- Mohamed Daouda Tolo (Shot Put - 15th in qualification, 20.65)

### Key Asian Rivals by Event (Named Athletes)

| Event | Athlete | Country | 2024-25 Best | Threat Level |
|-------|---------|---------|-------------|-------------|
| 100m | Sani Brown Abdul Hakim | JPN | 9.96 | High |
| 200m | Ryo Uzawa | JPN | 20.12 | High - ahead of Atafi |
| 400m | Keisuke Nozawa | JPN | 44.44 | High |
| 400m | Kalinga Kumarage | SRI | 44.99 | High |
| 800m | Mohammad Aman | BRN | ~1:44 | Moderate |
| 1500m | Ryuji Iizawa | JPN | 3:41.76 | Level with Al-Subaie |
| Pole Vault | Ernest John Obiena | PHI | 5.90 | Very High |
| Triple Jump | Zhu Yaming | CHN | 17.33 | High |
| Triple Jump | Fang Yaoqing | CHN | 17.09 | High |
| Shot Put | Mostafa Amiri | IRI | 20.32 | Moderate - Tolo ahead |
| Hammer Throw | Wang Qi | CHN | 74.50 | High |
| Javelin | Neeraj Chopra | IND | 88.88 | Dominant |
| High Jump | Mutaz Essa Barshim | QAT | 2.35 | Dominant |

### LA 2028 Olympic Pathway

**Realistic LA 2028 qualifiers (already at standard or close):**
1. Nasser Mohamed Abdo - 100m (QUALIFIED, 9.80)
2. Abdulaziz Abdou Atafi - 200m (QUALIFIED, 20.14)
3. Albaraa Alqarni - 800m (QUALIFIED, 1:35.49)
4. Mohamed Daouda Tolo - Shot Put (QUALIFIED, 21.80 vs 21.35)
5. Hussain Al-Hizam - Pole Vault (5.72, needs 5.82 - gap: 10cm)
6. Sami Bakhit - Triple Jump (16.98, needs 17.22 - gap: 24cm)

**Long-term development targets (2-3 year timeline):**
- Mazen Al-Yassin / Ibrahim Futayni - 400m (need ~44.90)
- Ali Baqer Al Jumah - 110mH (13.78, needs 13.27 - fast progression)
- Mohammed Al-Dubaisi - Hammer Throw (70.77, needs 78.50 - long gap)
- 4x100m Relay (39.18 in 2024, needs ~38.00 level for Olympic final)

---

*Document generated for the Athletics Coaching Chatbot. Data sourced from Tilastopaja competition database, World Athletics standards, and the Team Saudi athletics analytics platform. Athlete profiles last updated: February 2026.*
