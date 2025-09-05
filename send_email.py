import time
import os
import json
import base64
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


from mailjet_rest import Client


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
    """
    Build a plain text summary of new project details.
    Each project is a dictionary with keys: reg_no, promoter_name, project_name.
    """
    lines = []
    lines.append("New RERA Projects Update:\n")
    for proj in projects:
        lines.append("Registration No: " + proj["reg_no"])
        lines.append("Promoter Name:   " + proj["promoter_name"])
        lines.append("Project Name:    " + proj["project_name"])
        lines.append("-" * 40)
    return "\n".join(lines)



def send_email_with_mailjet_text(sender_email, receiver_emails, subject, body,
                                 mailjet_api_key, mailjet_api_secret):
    """
    Send an email with plain text content using Mailjet.
    
    Parameters:
        sender_email (str): Sender's email address (verified in Mailjet).
        receiver_emails (list): A list of dictionaries with keys "Email" and "Name".
        subject (str): Email subject.
        body (str): Email body (plain text).
        mailjet_api_key (str): Your Mailjet API key.
        mailjet_api_secret (str): Your Mailjet API secret.
    """
    # Initialize Mailjet client
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
    
    # Send the email
    result = mailjet.send.create(data=data)
    print("Mailjet response status code:", result.status_code)
    print("Mailjet response:", result.json())

# ------------------- Main Script -------------------

def main():
  
    stored_identifier = load_stored_identifier() or "PRM/KA/RERA/1251/309/PR/070225/007490"
    print("Loaded stored identifier:", stored_identifier)
    
    # Setup Chrome options (adjust as needed)
    options = webdriver.ChromeOptions()
    # Uncomment the following line to run Chrome headless
    # options.add_argument("--headless")
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 10)
    
    try:
     
        URL = 'https://rera.karnataka.gov.in/viewAllProjects'
        driver.get(URL)
        print("Navigated to the RERA projects URL.")
        
    
        district_input = wait.until(EC.presence_of_element_located((By.ID, "projectDist")))
        district_value = "Bengaluru Urban"
        
        # Check if the input field is read-only or disabled
        readonly_attr = district_input.get_attribute("readonly")
        if readonly_attr or not district_input.is_enabled():
            print("District input field is read-only or disabled; using JavaScript to set its value.")
            driver.execute_script("arguments[0].value = arguments[1];", district_input, district_value)
        else:
            try:
                district_input.clear()
                district_input.send_keys(district_value)
            except Exception as e:
                print("Standard method failed, falling back to JavaScript. Exception:", e)
                driver.execute_script("arguments[0].value = arguments[1];", district_input, district_value)
        print("Entered district:", district_value)
        
      
        search_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "btn-style")))
        search_button.click()
        print("Clicked search button.")
        
        # ------------------------------------------------------------
        # 4. Wait for the approved projects table to load (ID: approvedTable)
        # ------------------------------------------------------------
        wait.until(EC.presence_of_element_located((By.XPATH, '//table[@id="approvedTable"]')))
        print("Approved projects table loaded.")
        
        # ------------------------------------------------------------
        # 5. Trigger table sorting:
        #    a) Click the "STATUS" header once.
        #    b) Click the "APPROVED ON" header twice.
        # ------------------------------------------------------------
        status_header = wait.until(EC.element_to_be_clickable((By.XPATH, "//th[contains(text(), 'STATUS')]")))
        status_header.click()
        print("Clicked 'STATUS' header once.")
        time.sleep(2)  # Allow time for sorting animation
        
        approved_header = wait.until(EC.element_to_be_clickable((By.XPATH, "//th[contains(text(), 'APPROVED ON')]")))
        approved_header.click()
        time.sleep(2)
        approved_header.click()
        print("Clicked 'APPROVED ON' header twice.")
        time.sleep(2)
        
        # ------------------------------------------------------------
        # 6. Process all rows in the table.
        #    For each row, if the RERA ID (column 3, index 2) is not the stored one,
        #    extract and save its details; stop processing when the stored identifier is encountered.
        # ------------------------------------------------------------
        rows = driver.find_elements(By.XPATH, '//table[@id="approvedTable"]/tbody/tr')
        print("Total rows found in table:", len(rows))
        new_projects = []
        
        # Iterate over rows from top (newest) downwards
        for row in rows:
            cells = row.find_elements(By.TAG_NAME, "td")
            if len(cells) < 6:
                continue  # Skip rows that do not have enough cells
            current_rera_id = cells[2].text.strip()
            if current_rera_id == stored_identifier:
                # Found the stored project; assume all subsequent rows are already processed.
                break
            # Otherwise, treat as a new project.
            reg_no = current_rera_id  # Column index 2
            promoter_name = cells[4].text.strip()  # Column index 4
            project_name = cells[5].text.strip()   # Column index 5
            new_projects.append({
                "reg_no": reg_no,
                "promoter_name": promoter_name,
                "project_name": project_name
            })
        
        # Print details for all new projects.
        if new_projects:
            print("New projects found:")
            for proj in new_projects:
                print("Scraped Details:")
                print("  Registration No:", proj["reg_no"])
                print("  Promoter Name:  ", proj["promoter_name"])
                print("  Project Name:   ", proj["project_name"])
                print("-" * 40)
        else:
            print("No new projects detected.")
        
        # ------------------------------------------------------------
        # 7. Update the stored identifier with the RERA ID of the first row.
        # ------------------------------------------------------------
        if rows:
            new_stored = rows[0].find_elements(By.TAG_NAME, "td")[2].text.strip()
            save_stored_identifier(new_stored)
            print("Stored identifier updated to:", new_stored)
        
        # ------------------------------------------------------------
        # 8. Build an email body and send an email regardless of new projects.
        # ------------------------------------------------------------
        if new_projects:
            email_body = build_projects_text(new_projects)
        else:
            email_body = "No new projects updated."
        
        print("Email body built:\n", email_body)
        
        # Email configuration for Mailjet:
        sender_email = "khushi@truestate.in"

        receiver_emails = [
            {"Email": "khushiatrey011@gmail.com", "Name": "Khushi"}
            
        ]


        subject = "New RERA Projects Update"
        
        # Your Mailjet API credentials 
        mailjet_api_key = "6b9b4e0d97de22386aaa1a51d9eed48a"
        mailjet_api_secret = "9d4b8b1bbad3e75b21ccf99b5d3e493b"
        
        # Send the email with the plain text content using Mailjet
        send_email_with_mailjet_text(sender_email, receiver_emails, subject, email_body,
                                     mailjet_api_key, mailjet_api_secret)
    
    except Exception as e:
        print("An error occurred:", e)
    finally:
        driver.quit()
        print("Browser closed.")

if __name__ == "__main__":
    main()

