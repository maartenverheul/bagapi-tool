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
# By the way, this script is version 1.8
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
import logging
import os
from datetime import datetime

# Init logging (source: https://stackoverflow.com/a/24507130/20928224)
if not os.path.exists("logs"):
    os.makedirs("logs")

log_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%d/%m/%Y %H:%M:%S')

# File to log to
logFile = datetime.now().strftime('logs/info_%H_%M_%d_%m_%Y.log')

# Setup File handler
file_handler = logging.FileHandler(logFile)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)

# Setup Stream Handler (i.e. console)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
stream_handler.setLevel(logging.INFO)

# Get the logger
app_log = logging.getLogger('root')
app_log.setLevel(logging.INFO)

# Add both Handlers
app_log.addHandler(file_handler)
app_log.addHandler(stream_handler)

logging.info("New run started")

# Check config
if config.api_key == "" or config.api_base_url == "" or config.csv_delimiter == "":
  logging.info("Fatal error: Invalid configuration in config.py.")

  # Quit app
  quit()

# Declare output
output_rows = []
output_failures = []
output_skips = []

# ==================================================================================
#                                    FILE PHASE
# ==================================================================================

# Open input.csv
with open('input.csv', newline='') as csvfile:

  reader = csv.DictReader(csvfile, delimiter=config.csv_delimiter)
  # Read it's content
  data = list(reader)

# ==================================================================================
#                                    DATA PHASE
# ==================================================================================

# Declare helper variables
row_count = len(data)
row_index = -1

# Log info
logging.info("Input file has been read.")
logging.info("- Read {0} rows".format(row_count))

# Check for valid data
if row_count == 0:
  
  # No data has been found
  logging.info("- Fatal error: no data found in input.csv")

  # Can't do anything now, quit program
  quit()
if row_count > 0 and data[0].get('huisnummer', '') == "":

  # Something is wrong with the data
  logging.info("- Fatal error: 'huisnummer' column is missing. Did you specify the right csv delimiter?".format(row_count))

  # Can't do anything now, quit program
  quit()

# Loop through each row in the csv

for row in data:

  row_index += 1
  logging.info('Processing row {0}/{1} ({2}%)'.format(row_index+1, row_count, round(row_index/row_count*100)))

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

  # Check if adress has already been processed based on postcode + huisnummer
  is_duplicate = False
  for output_row in output_rows:
    a = row['postcode'] + str(row['huisnummer']) + row['huisnummertoevoeging']
    b = output_row['postcode'] + str(output_row['huisnummer']) + output_row['huisnummertoevoeging']
    if a == b:
      is_duplicate = True
      output_row['is_invoer'] = True
      break

  if is_duplicate:
    logging.info("- Address already processed. Skipping row.")

    # Stop here, and continue with next row
    output_skips.append(row_index)
    continue

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
    logging.info('- Error: {1}'.format(row_index, adres_data['title']))

    # Stop here, and continue with the next row
    output_failures.append(row_index)
    continue

  # Check data

  # _embedded column won't be there if no results are given
  if adres_data.get('_embedded', '') == "":
    logging.info("- Error: address {0} was not found.".format(query))

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
  pandId = adres_object['pandIdentificaties'][0]
  nummeraanduiding = adres_object['nummeraanduidingIdentificatie']

  # Mechanism to check if search query found the right result
  full_huisnummer = str(huisnummer) + huisnummertoevoeging.lower()
  full_huisnummer_row = row['huisnummer'] + row['huisnummertoevoeging'].lower()

  # Check if pand has already been processed based on pandId
  for output_row in output_rows:
    if pandId == output_row['pandId']:
      is_duplicate = True
      output_row['is_invoer'] = True
      break 

  if is_duplicate:
    logging.info("- Pand already processed. Skipping row.")

    # Stop here, and continue with next row
    output_skips.append(row_index)
    continue

  if full_huisnummer != full_huisnummer_row: # Is mismatch
    logging.info("- Error: address was not found and so another address was returned by the API instead (expected huisnummer {0}, got {1}).".format(full_huisnummer_row, full_huisnummer))

    # Stop here, and continue with next row
    output_failures.append(row_index)
    continue

  # Log info
  friendly_address = "{0} {1}{2}, {3} {4}".format(korteNaam, huisnummer, huisnummertoevoeging, postcode, woonplaats);
  logging.info("- Address is: " + friendly_address)

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

  logging.info("- Found pand: {0}".format(pandId))

  # ==================================================================================
  #                                   GET PERCEEL
  # ==================================================================================

  # Init variables
  perceel_section = ""
  perceel_number = ""
  perceel_size = ""
  perceel_description = ""
  perceel_energy = ""

  # Optionally skip
  if not config.skip_perceel:

    # Body data to send with gob request
    perceel_request_data = {
      "bagId": nummeraanduiding,
      "selection": [
        {
          "code": "buurtstatistieken",
          "deliver": "partialProduct",
          "purposeLimitations": []
        }
      ],
      "includePdf": False
    }

    # Make request
    perceel_response = requests.post(
      config.gob_api_base_url + "report",
      json = perceel_request_data,
      headers = {
      'X-Api-Key': config.gob_api_key
      }
    )

    # Parse data from json
    perceel_data = perceel_response.json()

    if perceel_response.status_code != 200:
      # Something went wrong
      logging.info("- GOB API error on bagId \"{0}\": \"{1}\"".format(nummeraanduiding, perceel_data['message']))

    else:

      if 'general' in perceel_data['document']:

        # Take data needed
        perceelaanduiding = perceel_data['document']['general']['kadastraleAanduiding']['kadastraleAanduiding']
        perceel_section = perceelaanduiding.split()[1]
        perceel_number = perceelaanduiding.split()[2]
        perceel_size = float(perceel_data['document']['general']['size'])
        perceel_description = perceel_data['document']['general']['omschrijving']
        perceel_energy = perceel_data['document']['general']['energieLabel']

        # If no energielabel, make it empty instead of given text
        if "geen energielabel" in perceel_energy:
          perceel_energy = ""

      else:

        logging.info("- Perceel data for bagId \"{0}\" was not given".format(nummeraanduiding))


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
        'straat': korteNaam,
        'woonplaats': woonplaats,
        'pandId': pandId,
        'bouwjaar': bouwjaar,
        'sectie': perceel_section,
        'perceelnummer': perceel_number,
        'perceeloppervlakte': perceel_size,
        'perceelomschrijving': perceel_description,
        'perceel_energielabel': perceel_energy,
        'huisnummer': huisnummer,
        'huisnummertoevoeging': huisnummertoevoeging,
        'verblijfsobjectId': verblijfsobject['identificatie'],
        'oppervlakte': verblijfsobject['oppervlakte'],
        'gebruiksdoel': verblijfsobject['gebruiksdoelen'][0],
        'status': verblijfsobject['status'],
        'is_invoer': True
      })
        
    if verblijfsobjecten_count > 1: # Pand contains multiple verblijfsobjecten

      # Loop through each verblijfsobject in pand
      for verblijfsobject in verblijfsobjecten:

        # Write data to file
        output_rows.append({
          'postcode': verblijfsobject['_embedded']['heeftAlsHoofdAdres']['nummeraanduiding'].get('postcode', ''),
          'straat': korteNaam,
          'woonplaats': woonplaats,
          'pandId': pandId,
          'bouwjaar': bouwjaar,
          'sectie': perceel_section,
          'perceelnummer': perceel_number,
          'perceeloppervlakte': perceel_size,
          'perceelomschrijving': perceel_description,
          'perceel_energielabel': perceel_energy,
          'huisnummer': verblijfsobject['_embedded']['heeftAlsHoofdAdres']['nummeraanduiding'].get('huisnummer', ''),
          'huisnummertoevoeging': verblijfsobject['_embedded']['heeftAlsHoofdAdres']['nummeraanduiding'].get('huisletter', ''),
          'verblijfsobjectId': verblijfsobject['verblijfsobject'].get('identificatie', ''),
          'oppervlakte': verblijfsobject['verblijfsobject'].get('oppervlakte', ''),
          'gebruiksdoel': verblijfsobject['verblijfsobject'].get('gebruiksdoelen', [])[0],
          'status': verblijfsobject['verblijfsobject'].get('status', ''),
        })

        # Add column that indicates that a row was the original address
        full_verblijfsobject_huisnummer_row = str(output_rows[-1].get('huisnummer', '')) + output_rows[-1].get('huisnummertoevoeging', '').lower()
        output_rows[-1]['is_invoer'] = full_verblijfsobject_huisnummer_row == full_huisnummer

    # If count is not multiple of 100, there is probably more, 
    #   so continue loop to process next page.
    # Else, nothing to fetch so break the loop
    if verblijfsobjecten_count % 100 != 0:
      break

  logging.info("- Found {0} verblijfsobjecten at pand (spread over {1} pages)".format(verblijfsobjecten_count, verblijfsobjecten_page))

# ==================================================================================
#                                 OUTPUT PHASE
# ==================================================================================

# Open file to be written
with open('output.csv', 'w', newline='') as csvfile:
    
    # Define what params should be written to output csv
    fieldnames = ['postcode', 'huisnummer', 'huisnummertoevoeging', 'straat', 'woonplaats', 'pandId', 'bouwjaar', 'verblijfsobjectId', 'oppervlakte', 'gebruiksdoel', 'status', 'is_invoer', 'sectie', 'perceelnummer', 'perceeloppervlakte', 'perceelomschrijving', 'perceel_energielabel']

    writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore', delimiter=config.csv_delimiter)

    # Write header line & all the rows
    writer.writeheader()
    writer.writerows(output_rows)

# Log info
logging.info("Processing done (100%)")
logging.info("- Written {0} csv rows (Input: {1} failed & {2} skipped duplicates)".format(len(output_rows), len(output_failures), len(output_skips)))

# Log failed rows
if len(output_failures) > 0:
  logging.info("- Failed input row number(s): " + ", ".join(map(lambda a : str(a+1),output_failures)))

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