import os
import glob
import orjson
from jinja2 import Environment, FileSystemLoader
import statistics
import base64
import imageio
from collections import OrderedDict
import c19utils
import re
from datetime import date

url_mappings = {
  'https://coronaviruscolombia.gov.co/': 'https://coronaviruscolombia.gov.co/Covid19/index.html',
  'https://health.ri.gov/covid': 'https://health.ri.gov/covid/',
  'https://www.health.ny.gov/diseases/communicable/coronavirus/': 'https://coronavirus.health.ny.gov/home',
  'https://www.govt.nz/covid-19-novel-coronavirus/': 'https://covid19.govt.nz/',
  'https://en.ssi.dk': 'https://en.ssi.dk/',
  'https://arkartassituacija.gov.lv': 'https://arkartassituacija.gov.lv/',
  'https://www.bahamas.gov.bs': 'https://www.bahamas.gov.bs/',
  'https://www.mspas.gob.gt/index.php/noticias/coronavirus-2019-ncov': 'https://www.mspas.gob.gt/index.php/noticias/covid-19/coronavirus-2019-ncov',
  'https://www.mspas.gob.gt/index.php/noticias/covid-19/coronavirus-2019-ncov': 'https://www.mspas.gob.gt/index.php/noticias/coronavirus-2019-ncov',
  'https://www.ontario.ca/page/2019-novel-coronavirus': 'https://covid-19.ontario.ca'
    }

# The lighthouse key isn't guaranteed to match the URL
# so allow for variance
def translate_to_lighthouse_key(lighthouse_keys, url):
  if url in lighthouse_keys:
    return url
  elif url_mappings[url] in lighthouse_keys:
    return url_mappings[url]
  return url

def get_reading_ages(language_directory):
  language_files_list = glob.glob(os.path.join(language_directory, "*.json"))
  latest_file = max(language_files_list, key=os.path.getctime)
  with open(latest_file) as lang_file:
    return orjson.loads(lang_file.read())

def get_map_of_lighthouse_data(lighthouse_folder):
  json_file_list = glob.glob(lighthouse_folder + '/*.json')
  combined = {}
  for json_file in json_file_list:
    try:
      json_data = open(json_file, "r").read()
      loaded_json = orjson.loads(json_data)
      url = loaded_json['finalUrl']
      if not url in combined.keys():
        combined[url] = []
      combined[url].append(json_file)
    except KeyError as e:
      raise e
  return combined

def get_date_indexed_lighthouse_data(json_file_list):
  parsed_data = {}

  for json_file in json_file_list:
    json_data = open(json_file, "r").read()
    loaded_json = orjson.loads(json_data)
    url = loaded_json['finalUrl']
    date = loaded_json['fetchTime'].split('T')[0]

    parsed_data[date] = loaded_json
  return parsed_data

# Produce a simplified version of the data we get from lighthouse reports.
# Returns a nested dictionary with scores for accessibility and speed
# in each case providing a score for each date since we started collecting
# data for that site.
#
# e.g { 'accessibility': { date(2020,05,01): '0.9', date(2020,05,02): '0.91' } ... }
def extract_scores(data, dates):
  dates.sort()
  first_date_parts = dates[0].split('-')
  first_date = date(int(first_date_parts[0]), int(first_date_parts[1]), int(first_date_parts[2]))
  last_date = date.today()

  output = {'accessibility': {}, 'speed': {}}
  for single_date in c19utils.daterange(first_date, last_date):
    str_date = single_date.strftime('%Y-%m-%d')
    try:
      output['accessibility'][str_date] = data[str_date]['categories']['accessibility']['score']
    except KeyError:
      output['accessibility'][str_date] = None

    try:
      output['speed'][str_date] = data[str_date]['categories']['performance']['score']
    except KeyError:
      output['speed'][str_date] = None

  return output

def calculate_scores(latest_date, extracted, data):
  calculations = {}

  extracted_speed = extracted['speed'].values()
  extracted_accessibility = extracted['accessibility'].values()

  extracted_speed = list(filter(None.__ne__, extracted_speed))
  extracted_accessibility = list(filter(None.__ne__, extracted_accessibility))

  try:
    if len(extracted_accessibility) > 0:
      calculations['max_accessibility'] = max(extracted_accessibility)
      calculations['average_accessibility'] = statistics.mean(extracted_accessibility)
      calculations['current_accessibility'] = data[latest_date]['categories']['accessibility']['score']
    if len(extracted_speed) > 0:
      calculations['max_speed'] = max(extracted_speed)
      calculations['average_speed'] = statistics.mean(extracted_speed)
      calculations['current_speed'] = data[latest_date]['categories']['performance']['score']
  except Exception as err:
    print(repr(err))
    print(f"Problem with {url}")
    raise err
  return calculations

def find_reading_age(language_data):
  try:
    reading_age = language_data['dragnet']['standard']
  except KeyError:
    try:
      reading_age = language_data['trafilatura']['standard']
    except KeyError:
      reading_age = None
  if reading_age == '-1th and 0th grade':
     reading_age = None
  return reading_age

def translate_reading_age(current_age):
  try:
    extracted_numbers = re.search(r'\d+', scores['reading age'])
    score_to_use = int(extracted_numbers.group())
    if score_to_use > 0 and score_to_use < 13:
        approx_age = score_to_use + 5
    elif score_to_use > 13:
        approx_age = 18
    else:
        approx_age = None
    return approx_age
  except:
    return None

def generate_timelapse(url_stub, root_directory, output_file):
  os.system(f"gm convert -loop 1 -delay 10 {root_directory}/**/{url_stub}.png {output_file}")
  return f"/timelapses/{url_stub}.gif"

def build_combined_rankings(avg_scores):
  rankings = { 'speed' : [], 'accessibility': []}
  for consideration in rankings:
    d_sorted_by_value = OrderedDict(sorted(avg_scores[consideration].items(), key=lambda x: x[1],  reverse=True))
    rankings[consideration] = d_sorted_by_value
  rankings['reading age'] = OrderedDict(sorted(avg_scores['reading age'].items(), key=lambda x: x[1]))
  return rankings

def build_top_table(site_list, rankings):
  top_table = {}
  site_count = len(site_list)
  for site in site_list:
    top_table[site] = {}

    try:
      top_table[site]['accessibility'] = rankings['accessibility'].get(site, '-')
      top_table[site]['speed'] = rankings['speed'].get(site, '-')
      top_table[site]['reading_age'] = rankings['reading age'].get(site, None)
    except KeyError as e:
      print(repr(e))

    try:
      top_table[site]['overall'] = 2 * (site_count - list(rankings['speed']).index(site))
    except ValueError as e:
      ''
    try:
      top_table[site]['overall'] += site_count - list(rankings['accessibility']).index(site)
    except ValueError as e:
      ''
    try:
      top_table[site]['overall'] += site_count - list(rankings['reading age']).index(site)
    except ValueError as e:
      ''
  return OrderedDict(sorted(top_table.items(), key=lambda x: x[1]['overall'], reverse=True))

def process_site(stripped_url, lighthouse_index, directories):
  scores = {}
  key = translate_to_lighthouse_key(lighthouse_index.keys(), stripped_url)
  site_data = get_date_indexed_lighthouse_data(lighthouse_index[key])

  dates_covered = list(site_data.keys())
  dates_covered.sort()
  latest_date = dates_covered[-1]

  extracted_scores = extract_scores(site_data, dates_covered)
  scores = calculate_scores(latest_date, extracted_scores, site_data)
  scores['over_time'] = extracted_scores
  return scores

def add_video_elements(scores, directories, clean_url):
  output_file = os.path.join(directories['timelapses'], clean_url + ".gif")
  scores['timelapse_filename'] = generate_timelapse(clean_url, directories['base'], output_file)
  video_filename = os.path.join(directories['reports'], "loading", clean_url + ".mp4")
  if os.path.exists(video_filename):
    scores['video_url'] = "/loading/" + clean_url + ".mp4"
  else:
    scores['video_url'] = False

directories = c19utils.establish_directories()

page_tmpl_file = os.path.join(directories['templates'], 'site.html')
index_tmpl_file = os.path.join(directories['templates'], 'index.html')

latest_language_data = get_reading_ages(directories['languages'])
lighthouse_index = get_map_of_lighthouse_data(directories['lighthouse'])
site_list = {}


if __name__ == "__main__":
  tmpl_env = Environment(loader=FileSystemLoader(directories['templates']))

  page_template = tmpl_env.get_template('site.html')
  index_template = tmpl_env.get_template('index.html')

  top_scores = {'accessibility' : {}, 'speed' : {}, 'reading age': {}}
  avg_scores = {'accessibility' : {}, 'speed' : {}, 'reading age': {}}

  for site in c19utils.CovidSiteList():
    stripped_url = site['URL']
    scores = {}
    clean_url = c19utils.filter_bad_filename_chars(stripped_url)
    url_stub = clean_url[0:100]

    try:
      scores = process_site(stripped_url, lighthouse_index, directories)
      add_video_elements(scores, directories, clean_url)
    except KeyError as e:
      print(f"No sign of lighthouse data for {stripped_url}")
      print(repr(e))
      next

    with open(os.path.join(directories['reports'], url_stub + ".html"), "w") as report:
      scores['site_name'] = stripped_url
      try:
        scores['reading age'] = find_reading_age(latest_language_data[stripped_url])
        scores['reading age'] = translate_reading_age(scores['reading age'])
        if scores['reading age']:
          avg_scores['reading age'][stripped_url] = scores['reading age']
      except KeyError:
        scores['reading age'] = None

      scores['reading_age'] = scores['reading age']
      output = page_template.render(scores)
      report.write(output)
      site_list[stripped_url] = { 'gov_name': site['Government name'], 'detail': "/" + url_stub + ".html" }

      top_scores['accessibility'][stripped_url] = scores.get('max_accessibility', 0)
      top_scores['speed'][stripped_url] = scores.get('max_speed', 0)
      avg_scores['accessibility'][stripped_url] = scores.get('average_accessibility', 0)
      avg_scores['speed'][stripped_url] = scores.get('average_speed', 0)
      print("Produced report for", url_stub)

  rankings = build_combined_rankings(avg_scores)
  sorted_rankings = build_top_table(site_list, rankings)

  index = index_template.render(sites = site_list, considerations = rankings, avg_scores = avg_scores, top_sites = sorted_rankings)
  with open(os.path.join(directories['reports'], "index.html"), "w") as index_file:
    index_file.write(index)
