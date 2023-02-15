# ==================================================================================
#                                       PREFACE
# ==================================================================================

# Dearest reader,
#
# Many tasks done by hand can be taken over by computers.
# They are fast, accurate, and don't have needs humans do.
# 
# Take a look at the following case. Thanks to an API many
# manhours can be spend in a better way. And boi is it fast.
#
# By the way, this script is version 1.6
# and is made by Maarten Verheul
#
# So, fasten your seatbelts, he we go:

# ==================================================================================
#                                 INITIATION PHASE
# ==================================================================================

# Import the required libraries

import requests # More information at https://realpython.com/python-requests/
import csv # More information at https://realpython.com/python-csv/
import config

# Check config
if config.api_key == "" or config.api_base_url == "":
  print("Fatal error: no API key or base url specified in config.py.")

  # Quit app

  quit()

# Declare static variables

csv_delimiter=';'

# Declare output

output_rows = []
output_failures = []

# ==================================================================================
#                                    FILE PHASE
# ==================================================================================

# Open input.csv

with open('input.csv', newline='') as csvfile:

  reader = csv.DictReader(csvfile, delimiter=csv_delimiter)
  # Read it's content

  data = list(reader)

# ==================================================================================
#                                    DATA PHASE
# ==================================================================================

# Declare helper variables

row_count = len(data)
row_index = -1

# User notification

print("Input file has been read.")
print("- Read {0} rows".format(row_count))

# Check for valid data

if row_count > 0 and data[0].get('huisnummer', '') == "":

  # Something is wrong with the data
  print("- Fatal error: 'huisnummer' column is missing. Did you specify the right csv delimiter?".format(row_count))

  # Can't do anything now, quit program
  quit()

# Loop through each row in the csv

for row in data:

  row_index += 1
  print('Processing row {0}/{1} ({2}%)'.format(row_index+1, row_count, round(row_index/row_count*100)))

  # ==================================================================================
  #                                    SEARCH FOR ADRES
  # ==================================================================================

  # Add all the parameters based on conditions

  params = {}

  if row.get('postcode', '') != "":

    # Postcode is given

    params['postcode'] = row['postcode']
    params['huisnummer'] = row['huisnummer']
    params['exacteMatch'] = 'true'

    query = '{0} {1}'.format(row['postcode'], row['huisnummer'])

    # Optionally add huisnummertoevoeging

    if row.get('huisnummertoevoeging', "") != "":
      params['huisletter'] = row['huisnummertoevoeging']

  else:

    # Postcode is not given, search based on query

    query = '{0} {1}{2}, {3}'.format(row['straat'], row['huisnummer'], row['huisnummertoevoeging'], row['stad'])
    params['q'] = query

  # Search request for the adres (according to https://lvbag.github.io/BAG-API/Technische%20specificatie/#/Adres/bevraagAdressen)

  adres_response = requests.get(
    config.api_base_url + "adressen",
    params=params,
    headers={
    'X-Api-Key': config.api_key
    }
  )

  # Parse the data. It's a JSON response, so use that

  adres_data = adres_response.json()

  # Check if the request went well

  if adres_response.status_code != 200:
    # Something went wrong
    
    print('- Error: {1}'.format(row_index, adres_data['title']))

    # Stop here, and continue with the next row

    output_failures.append(row_index)
    continue

  # Check data

  # _embedded column won't be there if no results are given
  if adres_data.get('_embedded', '') == "":
    print("- Error: address {0} was not found.".format(query))

    # Stop here, contiue on new row
    
    output_failures.append(row_index)
    continue

  # Get some data

  adres_object = adres_data['_embedded']['adressen'][0]
  korteNaam = adres_object['korteNaam']
  huisnummer = adres_object['huisnummer']
  woonplaats = adres_object['woonplaatsNaam']
  huisnummertoevoeging = adres_object.get('huisletter', '')
  postcode = adres_object['postcode']

  # Mechanism to check if search query found the right result
  
  full_huisnummer = str(huisnummer) + huisnummertoevoeging.lower()
  full_huisnummer_row = row['huisnummer'] + row['huisnummertoevoeging'].lower()

  if full_huisnummer != full_huisnummer_row: # Is mismatch
    print("- Error: address was not found and so another address was returned by the API instead (expected huisnummer {0}, got {1}).".format(full_huisnummer_row, full_huisnummer))

    # Stop here, and continue with next row

    output_failures.append(row_index)
    continue

  # User notification
  
  friendly_address = "{0} {1}{2}, {3} {4}".format(korteNaam, huisnummer, huisnummertoevoeging, postcode, woonplaats);
  print("- Address is: " + friendly_address)

  # ==================================================================================
  #                                    GET PAND
  # ==================================================================================

  # Get pand of adres (according to https://lvbag.github.io/BAG-API/Technische%20specificatie/#/Pand/pandIdentificatie)

  pand_response = requests.get(
    adres_object['_links']['panden'][0]['href'],
    headers={
    'X-Api-Key': config.api_key,
    'Accept-Crs': 'epsg:28992'
    }
  )

  # Parse json data

  pand_data = pand_response.json()

  # Get some data

  pandId = pand_data['pand']['identificatie']
  bouwjaar = pand_data['pand']['oorspronkelijkBouwjaar']

  print("- Found pand: {0}".format(pandId))

  # ==================================================================================
  #                           GET VERBLIJFSOBJECTEN AT PAND
  # ==================================================================================

  # Get verblijfsobjecten of pand (according to https://lvbag.github.io/BAG-API/Technische%20specificatie/#/Verblijfsobject/zoekVerblijfsobjecten)

  verblijfsobjecten_page = 0
  verblijfsobjecten_count = 0

  # Create seamingly infinite loop that gets broken where needed

  while True:

    verblijfsobjecten_page += 1

    verblijfsobjecten_response = requests.get(
      config.api_base_url + "verblijfsobjecten",
      params={
      'pandIdentificatie': pandId,
      'expand': 'heeftAlsHoofdAdres',
      'pageSize': 100, # Maximum of verblijfsobjecten per call
      'page': verblijfsobjecten_page
      },
      headers={
      'X-Api-Key': config.api_key,
      'Accept-Crs': 'epsg:28992'
      }
    )

    # Parse the data

    verblijfsobjecten_data = verblijfsobjecten_response.json()

    # If _embedded column, there were no objects on this 'page'
    if verblijfsobjecten_data.get('_embedded', '') == "":
      # Decrease page for logging
      verblijfsobjecten_page -= 1
      break

    verblijfsobjecten = verblijfsobjecten_data['_embedded']['verblijfsobjecten']
    verblijfsobjecten_count += len(verblijfsobjecten)

    # Data to be extracted:
    #
    # - Postcode
    # - PandID
    # - Bouwjaar
    #
    # For every verblijfsobject:
    #
    # - Verblijfsobject ID
    # - Huisnummer
    # - Oppervlakte
    # - Gebruiksdoel
    # - Status

    if verblijfsobjecten_count == 1: # Pand contains only a single verblijfsobject

        verblijfsobject = verblijfsobjecten[0]['verblijfsobject']
        output_rows.append({
        'postcode': postcode,
        'huisnummer': huisnummer,
        'huisnummertoevoeging': huisnummertoevoeging,
        'straat': korteNaam,
        'pandId': pandId,
        'bouwjaar': bouwjaar,
        'verblijfsobjectId': verblijfsobject['identificatie'],
        'oppervlakte': verblijfsobject['oppervlakte'],
        'gebruiksdoel': verblijfsobject['gebruiksdoelen'][0],
        'status': verblijfsobject['status'],
      })
        
    if verblijfsobjecten_count > 1: # Pand contains multiple verblijfsobjecten

      # Loop through each verblijfsobject in pand

      for verblijfsobject in verblijfsobjecten:

        # Write data to file

        output_rows.append({
          'postcode': verblijfsobject['_embedded']['heeftAlsHoofdAdres']['nummeraanduiding'].get('postcode', ''),
          'huisnummer': verblijfsobject['_embedded']['heeftAlsHoofdAdres']['nummeraanduiding'].get('huisnummer', ''),
          'huisnummertoevoeging': verblijfsobject['_embedded']['heeftAlsHoofdAdres']['nummeraanduiding'].get('huisletter', ''),
          'straat': korteNaam,
          'pandId': pandId,
          'bouwjaar': bouwjaar,
          'verblijfsobjectId': verblijfsobject['verblijfsobject'].get('identificatie', ''),
          'oppervlakte': verblijfsobject['verblijfsobject'].get('oppervlakte', ''),
          'gebruiksdoel': verblijfsobject['verblijfsobject'].get('gebruiksdoelen', [])[0],
          'status': verblijfsobject['verblijfsobject'].get('status', ''),
        })

    # If count is not multiple of 100, there is probably more, 
    #   so continue loop to process next page.
    # Else, nothing to fetch so break the loop

    if verblijfsobjecten_count % 100 != 0:
      break

  print("- Found {0} verblijfsobjecten at pand (spread over {1} pages)".format(verblijfsobjecten_count, verblijfsobjecten_page))

# ==================================================================================
#                                 OUTPUT PHASE
# ==================================================================================

# Open file to be written

with open('output.csv', 'w', newline='') as csvfile:
    
    # Define what params should be written to output csv

    fieldnames = ['postcode', 'huisnummer', 'huisnummertoevoeging', 'straat', 'pandId', 'bouwjaar', 'verblijfsobjectId', 'oppervlakte', 'gebruiksdoel', 'status']

    writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore', delimiter=csv_delimiter)

    # Write header line & all the rows

    writer.writeheader()
    writer.writerows(output_rows)

# User notification

print("Processing done!")
print("- Written {0} csv rows ({1} failed rows were not written)".format(len(output_rows), len(output_failures)))

if len(output_failures) > 0:
  print("- Failed input row number(s): " + ", ".join(map(lambda a : str(a+1),output_failures)))

# ==================================================================================
#                                       EPILOGUE
# ==================================================================================

# Well, well, then this journey has come
# to an end. I hope you will have fun with it.
#
# With ease,
# 𝓜𝓪𝓪𝓻𝓽𝓮𝓷
#
# Hmmm, time for some coffee.
#                               ░░              ░░              ░░                                
#                               ░░              ░░              ░░                                
#                                 ░░              ░░              ░░                              
#                                 ░░              ░░              ░░                              
#                               ░░              ░░              ░░                                
#                               ░░              ░░              ░░                                
#                             ░░              ░░              ░░                                  
#                             ░░              ░░              ░░                                  
#                               ░░              ░░              ░░                                
#                               ░░              ░░              ░░                                
#                                 ░░              ░░              ░░                              
#                                 ░░              ░░              ░░                              
#                               ░░              ░░              ░░                                
#                               ░░              ░░              ░░                                
#                                                                                                 
#                                     ▓▓██████████████████████                                    
#                             ████████                        ████████                            
#                         ████        ████████████████████████        ████                        
#                       ██░░    ██████▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒▒██▓▓██  ░░░░██                      
#                     ██    ████▒▒▓▓▓▓▓▓▓▓░░░░░░▓▓▓▓░░░░░░▓▓▓▓▒▒▓▓▓▓████    ██                    
#                   ██    ██▓▓▓▓▓▓▓▓▓▓▓▓░░▓▓▓▓▓▓░░░░▓▓▓▓▓▓░░▓▓▓▓▓▓▓▓▒▒▓▓██    ██                  
#                   ██  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░▓▓▓▓▓▓▓▓▓▓▒▒▓▓▓▓  ██  ██▓▓▓▓▓▓██      
#                   ██  ██▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░▓▓▓▓▓▓▓▓▓▓▓▓░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▒▒██  ████          ██    
#                   ██    ██▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░▓▓▓▓▓▓▓▓░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓██    ██              ██  
#                     ██  ░░████▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓████░░  ██░░    ████      ██  
#                     ██        ██████▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓██████        ██  ████    ██    ██  
#                     ██              ████████████████████████              ████        ██    ██  
#                     ██                ░░  ░░░░░░░░░░░░░░░░░░              ██          ██    ██  
#                 ██████                                                    ██████    ██      ██  
#             ████    ██                                                    ██    ██  ██    ██    
#         ░░██▒▒░░    ▒▒▓▓                                                ▓▓▒▒    ░░██▒▒    ██    
#       ▓▓  ░░          ██                                                ██  ██████      ▓▓      
#     ██                ██                                                ████        ████  ██    
#   ██                  ░░██                                            ██░░░░    ████░░░░  ░░██  
#   ██                ██████                                            ██████████░░░░        ██  
# ██                ██▒▒░░▒▒██                                        ██▒▒▒▒██                  ██
# ██              ██▒▒██▒▒▒▒██                                        ██▒▒▒▒▒▒██                ██
# ██              ██░░▓▓████▒▒▓▓                                    ▓▓▒▒██░░▒▒██                ██
#   ██            ██▒▒██▓▓░░▒▒▒▒██                                ██▒▒░░▒▒████                ██  
#   ██              ██░░██▒▒████▒▒████                        ████▒▒██▒▒██▒▒██                ██  
#     ██            ██▒▒▒▒██▓▓░░▒▒░░▒▒██▓▓▓▓            ▓▓▓▓██▒▒██▒▒░░██▒▒░░██              ██    
#       ██            ██████▒▒▒▒▒▒██████▒▒▒▒████████████▒▒██▒▒▒▒▓▓██▒▒▒▒████░░            ██      
#         ██                ██████░░▒▒██░░▒▒██▒▒▒▒░░▒▒██▒▒▒▒██░░▒▒▒▒████                ██        
#           ████                ██▒▒▒▒▓▓▒▒▒▒██░░▒▒████▒▒░░▒▒▒▒██████                ████          
#           ░░  ████              ████  ████░░████░░░░████████    ░░            ████              
#                   ████                                                    ████                  
#                       ██▓▓▓▓██                                    ▓▓▓▓▓▓██                      
#                               ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓                              