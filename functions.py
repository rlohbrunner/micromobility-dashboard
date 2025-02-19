def get_valid_cities():
    global valid_cities  # Access the global variable
    if 'valid_cities' in globals():
        if valid_cities is not None:
            return valid_cities  # Return the cached list
    else:
        valid_cities = None

    # Select Webpage
    url = "https://public.ridereport.com"

    # Initialize WebDriver
    driver = webdriver.Chrome(options=chrome_options)

    # Load Webpage
    driver.get(url)
    time.sleep(0.1)  # Allow time for page to load

    # Get List of Valid Cities
    soup = BeautifulSoup(driver.page_source, "html.parser")
    city_elements = soup.find_all("span", class_="ComparisonChartTableRow_cityName__GhFPE")
    valid_cities = [city.get_text(strip=True) for city in city_elements]
    valid_cities = sorted(valid_cities)
    city_labels = soup.find_all("label", attrs={'for': True})  # Get labels with 'for' attribute
    cities_from_labels = [label["for"].strip() for label in city_labels]

    # Return Valid Cities List
    return {valid_cities: cities_from_labels}
def prep_website():
  # Initialize WebDriver
  driver = webdriver.Chrome(options=chrome_options)

  # Load Webpage
  driver.get(url)
  time.sleep(0.1)  # Allow time for page to load

  # Deselect Washington, DC & Denver
  try:
      selected_cities = driver.find_elements(By.XPATH, "//input[@type='checkbox'][@checked]")  # Find all selected checkboxes
      for cities in selected_cities:
          driver.execute_script("arguments[0].click();", cities)  # Deselect using JavaScript
          time.sleep(0.1)  # Small delay for UI update
  except Exception as e:
      print("Error deselecting cities:", e)
def search_city(city):
  # Search for city in the search box
  city_label = valid_cities[city]
  try:
      search_box = WebDriverWait(driver, 10).until(
          EC.presence_of_element_located((By.XPATH, "//input[contains(@class, 'IndexSearchFilterControl_searchBarInput')]"))
      )
      search_box.clear()
      search_box.send_keys(city)
      time.sleep(0.1)
  except Exception as e:
      print("Error finding search box:", e)
      driver.quit()
      exit()

  # Select the city checkbox
  try:
      city_checkbox = WebDriverWait(driver, 10).until(
          EC.element_to_be_clickable((By.XPATH, "//label[@for='{city_label}']"))
      )
      driver.execute_script("arguments[0].click();", city_checkbox)  # Click via JavaScript
      time.sleep(0.1)
  except Exception as e:
      print("Error selecting {city}:", e)
      driver.quit()
      exit()

  # Close the filter dropdown by pressing 'ESC'
  search_box.send_keys(Keys.ESCAPE)
  time.sleep(0.1)
def find_chart():
  # Hover over the chart to trigger tooltip
  surface_element = WebDriverWait(driver, 10).until(
      EC.presence_of_element_located((By.CLASS_NAME, "recharts-surface"))
  )

  # Extract SVG surface x, y, width, height values
  s_x = int(surface_element.location["x"])
  s_y = int(surface_element.location["y"])
  s_width = int(surface_element.size["width"])
  s_height = int(surface_element.size["height"])

  # Compute data slices
  n_slices = n_steps
  x_start = -s_width//2+s_x
  x_end = s_width//2+s_x+10
  x_positions = list(range(x_start, x_end, int((x_end - x_start) / n_slices)))
def get_data():
  # Creates array for storing data
  tooltip_data = []
  # Activates selenium action chain
  actions = ActionChains(driver)
  for x_position in x_positions:
    try:
        #print(f"Moving cursor to: ({x_position}, {0})")  # Debug position
        actions.move_to_element_with_offset(surface_element, x_position, 0).perform()
        # Extract tooltip data
        soup = BeautifulSoup(driver.page_source, "html.parser")
        tooltip_list = soup.find("ul", class_="recharts-tooltip-item-list")
        tooltip_label = soup.find("p", class_="recharts-tooltip-label")
        date = tooltip_label.text.strip()
        if tooltip_list:
            for item in tooltip_list.find_all("li", class_="recharts-tooltip-item"):
                name = item.find("span", class_="recharts-tooltip-item-name").text.strip()
                value = item.find("span", class_="recharts-tooltip-item-value").text.strip()
                tooltip_data.append({"Date": date, "City": name, "Trips": value})
    except Exception as e:
        print("Error moving cursor:", e)
    # Convert to DataFrame
    df = pd.DataFrame(tooltip_data)
    #return output
    return df



