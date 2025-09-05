import time
import os
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from mailjet_rest import Client
from selenium.common.exceptions import NoSuchElementException

# ---------- Helper Functions ----------

def load_stored_identifier(filename="stored_identifier.json"):
    """Load the stored RERA ID from a JSON file (if it exists)."""
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                return data.get("stored_identifier")
            except json.JSONDecodeError:
                print("JSON decode error. Returning None.")
                return None
    return None

def save_stored_identifier(identifier, filename="stored_identifier.json"):
    """Save the given RERA ID to a JSON file."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump({"stored_identifier": identifier}, f, indent=4)

def build_projects_text(projects):
    """Build a plain text summary of new project details."""
    lines = ["New RERA Projects Update:\n"]
    for proj in projects:
        lines.append("Registration No:      " + proj["reg_no"])
        lines.append("Promoter Name:        " + proj["promoter_name"])
        lines.append("Project Name:         " + proj["project_name"])
        lines.append("Address:              " + proj.get("address", "N/A"))
        lines.append("Project Type:         " + proj.get("project_type", "N/A"))
        lines.append("Project Sub Type:     " + proj.get("project_sub_type", "N/A"))
        # lines.append("Total Area:           " + proj.get("total_area", "N/A"))
        lines.append("Total Inventories:    " + proj.get("total_units", "N/A"))
        lines.append("Completion Date:      " + proj.get("proposed_completion_date", "N/A"))
        lines.append("Latitude:             " + proj.get("latitude", "N/A"))
        lines.append("Longitude:            " + proj.get("longitude", "N/A"))
        lines.append("Covered Parking:      " + proj.get("covered_parking", "N/A"))
        lines.append("Total Open Area:      " + proj.get("total_open_area", "N/A"))
        lines.append("Total Land Area:      " + proj.get("total_land_area", "N/A"))
        lines.append("Number of Towers:     " + proj.get("number_of_towers", "N/A"))
        
        # Add inventory details if available
        if "inventory_details" in proj and proj["inventory_details"]:
            lines.append("\nInventory Details:")
            lines.append("Type | Count | Carpet Area | Balcony Area | Terrace Area")
            lines.append("-" * 70)
            for inv in proj["inventory_details"]:
                lines.append(f"{inv['type']} | {inv['count']} | {inv['carpet_area']} | {inv['balcony_area']} | {inv['terrace_area']}")
        
        lines.append("-" * 40)
    return "\n".join(lines)

def send_email_with_mailjet_text(sender_email, receiver_emails, subject, body,
                                 mailjet_api_key, mailjet_api_secret):
    """Send an email with plain text content using Mailjet."""
    mailjet = Client(auth=(mailjet_api_key, mailjet_api_secret), version='v3.1')
    data = {
        'Messages': [
            {
                "From": {
                    "Email": sender_email,
                    "Name": "No Reply"
                },
                "To": receiver_emails,
                "Subject": subject,
                "TextPart": body,
                "HTMLPart": f"<pre>{body}</pre>"
            }
        ]
    }
    result = mailjet.send.create(data=data)
    print("Mailjet response status code:", result.status_code)
    print("Mailjet response:", result.json())

def apply_filters(driver, wait):
    """Apply all required filters to get the desired project list."""
    # Enter district
    district_input = wait.until(EC.presence_of_element_located((By.ID, "projectDist")))
    district_value = "Bengaluru Urban"
    
    readonly_attr = district_input.get_attribute('readonly')
    if readonly_attr or not district_input.is_enabled():
        driver.execute_script("arguments[0].value = arguments[1];", district_input, district_value)
    else:
        try:
            district_input.clear()
            district_input.send_keys(district_value)
        except Exception:
            driver.execute_script("arguments[0].value = arguments[1];", district_input, district_value)
    
    print("Entered district:", district_value)
    
    # Click search
    search_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "btn-style")))
    search_button.click()
    print("Clicked search button.")
    
    # Wait for results table
    wait.until(EC.presence_of_element_located((By.XPATH, '//table[@id="approvedTable"]')))
    print("Approved projects table loaded.")
    
    # Sort by STATUS and then by APPROVED ON
    status_header = wait.until(EC.element_to_be_clickable((By.XPATH, "//th[contains(text(), 'STATUS')]")))
    status_header.click()
    print("Clicked 'STATUS' header once.")
    time.sleep(2)
    
    approved_header = wait.until(EC.element_to_be_clickable((By.XPATH, "//th[contains(text(), 'APPROVED ON')]")))
    approved_header.click()
    time.sleep(2)
    approved_header.click()
    print("Clicked 'APPROVED ON' header twice.")
    time.sleep(2)

def is_on_main_page(driver):
    """Check if we're on the main search page or results page."""
    try:
        # Check for approvedTable which indicates results page
        driver.find_element(By.ID, "approvedTable")
        return False
    except NoSuchElementException:
        # No table found, likely on main page
        return True

def safe_text(driver, xpath):
    """Safely extract text from an element, returning N/A if not found."""
    try:
        elements = driver.find_elements(By.XPATH, xpath)
        if elements:
            return elements[0].text.strip()
        return "N/A"
    except Exception:
        return "N/A"

# ---------- Main Script ----------

def main():
    stored_identifier = load_stored_identifier() or "PRM/KA/RERA/1251/309/PR/070225/007490"
    print("Loaded stored identifier:", stored_identifier)

    options = webdriver.ChromeOptions()
    # options.add_argument("--headless")  # Uncomment to run in background
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 10)

    try:
        URL = 'https://rera.karnataka.gov.in/viewAllProjects'
        driver.get(URL)
        print("Navigated to the RERA projects URL.")

        # Apply initial filters
        apply_filters(driver, wait)

        new_projects = []
        newest_rera_id = None
        processed_ids = set()  # Track already processed IDs to avoid duplication
        
        # Continue until we find the stored identifier or run out of rows
        found_stored_identifier = False
        while not found_stored_identifier:
            # Check if we're on the main page and need to reapply filters
            if is_on_main_page(driver):
                print("Detected main page, reapplying filters...")
                apply_filters(driver, wait)
            
            # Get all current rows
            rows = driver.find_elements(By.XPATH, '//table[@id="approvedTable"]/tbody/tr')
            if not rows:
                print("No rows found, stopping processing.")
                break
                
            # Process each row until we find the stored identifier
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) < 6:
                    continue  # Skip rows that don't have enough cells
                
                current_rera_id = cells[2].text.strip()
                
                # Skip already processed projects
                if current_rera_id in processed_ids:
                    continue
                
                # Set the first project we encounter as the "newest" one to update later
                if newest_rera_id is None:
                    newest_rera_id = current_rera_id
                    print(f"Set newest RERA ID to: {newest_rera_id}")
                
                # If we encounter the stored identifier, stop processing after this point
                if current_rera_id == stored_identifier:
                    print(f"Found stored identifier: {stored_identifier}. Stopping processing.")
                    found_stored_identifier = True
                    break
                
                reg_no = current_rera_id
                promoter_name = cells[4].text.strip()
                project_name = cells[5].text.strip()
                print(f"Processing project: {project_name} (Reg: {reg_no})")
                
                try:
                    # Add to processed IDs list before processing to ensure we don't repeat
                    processed_ids.add(current_rera_id)
                    
                    detail_button = row.find_element(By.XPATH, ".//a[contains(@onclick, 'showFileApplicationPreview')]")
                    driver.execute_script("arguments[0].click();", detail_button)
                    print(f"Clicked 'View Project Details' for project {reg_no}")
                    
                    details_tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@data-toggle='tab'][@href='#menu2']")))
                    driver.execute_script("arguments[0].click();", details_tab)
                    print(f"'Project Details' tab clicked for project {reg_no}")
                    time.sleep(3)  # Increased wait time to ensure content loads
                    
                    # Fixed XPath expressions that match the HTML structure
                    address = safe_text(driver, "//p[contains(text(),'Project Address')]/parent::div/following-sibling::div/p")
                    proposed_completion_date = safe_text(driver, "//p[text()='Proposed Completion Date']/parent::div/following-sibling::div/p")
                    latitude = safe_text(driver, "//p[text()='Latitude']/parent::div/following-sibling::div/p")
                    longitude = safe_text(driver, "//p[text()='Longitude']/parent::div/following-sibling::div/p")
                    covered_parking = safe_text(driver, "//p[contains(text(),'No. of Covered Parking')]/parent::div/following-sibling::div/p")
                    total_open_area = safe_text(driver, "//p[contains(text(),'Total Open Area')]/parent::div/following-sibling::div/p")
                    total_land_area = safe_text(driver, "//p[contains(text(),'Total Area Of Land')]/parent::div/following-sibling::div/p")
                    
                    # Additional details
                    project_type = safe_text(driver, "//label[contains(text(),'Project Type')]/parent::div/following-sibling::div/p") or safe_text(driver, "//p[contains(text(),'Project Type')]/parent::div/following-sibling::div/p")
                    project_sub_type = safe_text(driver, "//p[contains(text(),'Project Sub Type')]/parent::div/following-sibling::div/p")
                    total_area = safe_text(driver, "//p[contains(text(),'Total Area')]/parent::div/following-sibling::div/p")
                    total_units = safe_text(driver, "//p[contains(text(),'Total Number of Inventories') or contains(text(),'Total Number of Flats') or contains(text(),'Total Number of Villas')]/parent::div/following-sibling::div/p")
                    number_of_towers = safe_text(driver, "//p[contains(text(),'Number of Towers')]/parent::div/following-sibling::div/p")
                    
                    # FIXED INVENTORY EXTRACTION CODE
                    inventory_details = []
                    seen_first_sl_no = False
                    try:
                        inventory_rows = driver.find_elements(By.XPATH, "//table[contains(@class, 'table-bordered')]/tbody/tr")
                        for inv_row in inventory_rows:
                            cols = inv_row.find_elements(By.TAG_NAME, "td")
                            if len(cols) >= 6:  # Ensure we have enough columns
                                # Skip rows where all columns are empty
                                if all(not c.text.strip() for c in cols):
                                    continue
                                    
                                sl_no = cols[0].text.strip()
                                
                                # If we see Serial No. 1 for a second time, stop processing
                                if sl_no == "1" and seen_first_sl_no:
                                    break
                                    
                                # If this is the first time seeing Serial No. 1, mark it
                                if sl_no == "1":
                                    seen_first_sl_no = True
                                
                                inventory_type = cols[1].text.strip()
                                inventory_count = cols[2].text.strip()
                                carpet_area = cols[3].text.strip()
                                balcony_area = cols[4].text.strip()
                                terrace_area = cols[5].text.strip()
                                
                                # Only add rows that have non-empty data
                                if inventory_type and inventory_count:
                                    inventory_details.append({
                                        "type": inventory_type,
                                        "count": inventory_count,
                                        "carpet_area": carpet_area,
                                        "balcony_area": balcony_area,
                                        "terrace_area": terrace_area
                                    })
                    except Exception as e:
                        print(f"Error extracting inventory details: {e}")
                    
                    new_projects.append({
                        "reg_no": reg_no,
                        "promoter_name": promoter_name,
                        "project_name": project_name,
                        # "project_type": project_type,
                        "address": address,
                        "project_sub_type": project_sub_type,
                        "total_area": total_area,
                        "total_units": total_units,
                        "proposed_completion_date": proposed_completion_date,
                        "latitude": latitude,
                        "longitude": longitude,
                        "covered_parking": covered_parking,
                        "total_open_area": total_open_area,
                        "total_land_area": total_land_area,
                        "number_of_towers": number_of_towers,
                        "inventory_details": inventory_details
                    })
                    print(f"Added project {project_name} to new_projects list")
                    
                    # After viewing details, return to the main page
                    driver.back()
                    print(f"Navigated back from project details")
                    time.sleep(5)  # Wait for the page to reload
                    
                    # Break the inner loop to recheck the page state
                    break
                    
                except Exception as e:
                    print(f"Could not extract detailed info for project {reg_no}: {e}")
                    continue
            
            # If no more rows to process or found the identifier, exit the loop
            if found_stored_identifier or not row:
                break
        
        # Save the latest (topmost) new RERA ID after scraping all projects
        if newest_rera_id:
            save_stored_identifier(newest_rera_id)
            print("Stored identifier updated to:", newest_rera_id)
        
        # Send email with all the new projects
        email_body = build_projects_text(new_projects) if new_projects else "No new projects updated."
        sender_email = "khushiatrey011@gmail.com"
        receiver_emails = [
            {"Email": "khushi@truestate.in", "Name": "Khushi"},
            {"Email": "raman@truestate.in", "Name": "Raman"},
            {"Email": "siddharth@truestate.in", "Name": "Sidharth"},
           
        ]
        subject = "New RERA Projects Update"
        mailjet_api_key = "ecad4f02175cc06bb5af8c45b1ed11b0"
        mailjet_api_secret = "05a81d3b2447bb0d73eb936fa680224e"
        
        send_email_with_mailjet_text(sender_email, receiver_emails, subject, email_body,
                                    mailjet_api_key, mailjet_api_secret)
    
    except Exception as e:
        print("An error occurred:", e)
    finally:
        driver.quit()
        print("Browser closed.")

if __name__ == "__main__":
    main()
