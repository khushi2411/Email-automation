import asyncio
import csv
from playwright.async_api import async_playwright
import time
import json
import os

class GmailEmailSender:
    def __init__(self):
        self.sender_email = "khushiatrey012@gmail.com"
        self.to_emails = ["Lmt@embassyindia.com", "kevin.m@embassyindia.com","mohsin.j@embassyindia.com"]
        self.cc_emails = ["mohsin.j@embassyindia.com"]
        self.compose_selector = None  
        self.session_file = "gmail_session.json"
    
    async def save_session(self, context):
  
        try:
            
            cookies = await context.cookies()
            
      
            with open(self.session_file, 'w') as f:
                json.dump(cookies, f)
            
            print(f"Session saved to {self.session_file}")
        except Exception as e:
            print(f"Could not save session: {e}")
    
    async def load_session(self, context):
        """Load previously saved session"""
        try:
            if os.path.exists(self.session_file):
                with open(self.session_file, 'r') as f:
                    cookies = json.load(f)
           
                await context.add_cookies(cookies)
                print("Previous session loaded")
                return True
        except Exception as e:
            print(f"Could not load session: {e}")
        return False
    
    def wait_for_user_confirmation(self, message):
       
        input(f"\n{message}\nPress Enter to continue...")
    
    def create_email_content(self, name, phone_number):
    
        subject = "Lead Registration for Embassy Green Shore / Embassy Edge| IQOL Technologies"
        
        body = f"""Hi Team,

Please register the below lead for the project :- 
Embassy Green Shore / Embassy Edge

Name :- {name}
Contact :- {phone_number}

Regards,
Canvas Homes (IQOL Technologies Pvt Ltd)

Agent Name :- Yashwanth.S
Agent's Phone Number :- 9353329893"""
        
        return subject, body
    
    async def login_to_gmail(self, page, context):
      
        print("Opening Gmail...")
        await page.goto("https://mail.google.com")
        
        # Wait for page to load
        await page.wait_for_timeout(5000)
        
        print("Checking if logged in...")
        
        
        compose_selectors = [
            'div.T-I.T-I-KE.L3:has-text("Compose")',  
            '[gh="cm"]',  
            'div[role="button"]:has-text("Compose")',  
            '.T-I.T-I-KE.L3',  
            'div:has-text("Compose")'  
        ]
        
     
        for selector in compose_selectors:
            try:
                await page.wait_for_selector(selector, timeout=3000)
                print(f"Already logged in! Found compose button: {selector}")
                self.compose_selector = selector
                return True
            except:
                continue
        
        
        print("\n" + "="*60)
        print("MANUAL LOGIN REQUIRED")
        print("="*60)
        print("Please log in to Gmail in the browser window.")
        print("Complete the login process including any 2FA if required.")
        
   
        self.wait_for_user_confirmation("After logging in successfully")
        
       
        print("Checking if login was successful...")
        for attempt in range(3):
            print(f"Attempt {attempt + 1}/3...")
            
            for selector in compose_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=5000)
                    print(f"Login successful! Found compose button: {selector}")
                    self.compose_selector = selector
                    
                    # Save session for future use
                    await self.save_session(context)
                    return True
                except:
                    continue
            
            if attempt < 2:
                print("Compose button not found, waiting a bit more...")
                await page.wait_for_timeout(3000)
        
        print("Could not detect successful login. Please ensure:")
        print("1. You are logged into Gmail")
        print("2. Gmail interface is fully loaded")
        print("3. You can see the Compose button")
        return False
    
    async def compose_and_send_email(self, page, name, phone_number, row_number):
        """Compose and send a single email"""
        try:
            subject, body = self.create_email_content(name, phone_number)
            
            print(f"Composing email {row_number} for {name}")
            
            # Click Compose button using the detected working selector
            if not self.compose_selector:
                print("No working compose selector found")
                return False
                
            await page.wait_for_selector(self.compose_selector, timeout=10000)
            await page.click(self.compose_selector)
            
            # Wait for compose window to open
            await page.wait_for_timeout(3000)
            
            # Fill TO field with both recipients
            print("Adding TO recipients...")
            to_selectors = [
                'input[peoplekit-id="BbVjBd"]',
                'textarea[name="to"]',
                'input[name="to"]',
                'div[data-name="to"] input'
            ]
            
            to_field_found = False
            for to_selector in to_selectors:
                try:
                    await page.wait_for_selector(to_selector, timeout=5000)
                    
                    # Add all TO recipients as a single string
                    all_to_emails = ", ".join(self.to_emails)
                    await page.fill(to_selector, all_to_emails)
                    await page.keyboard.press('Tab')
                    await page.wait_for_timeout(1000)
                    
                    print(f"Added TO recipients: {all_to_emails}")
                    to_field_found = True
                    break
                except:
                    continue
            
            if not to_field_found:
                print("Could not find TO field")
                return False
            
            # Try to add CC recipients (optional - don't fail if it doesn't work)
            print("Attempting to add CC recipients...")
            try:
                # Try different ways to access CC
                cc_button_selectors = [
                    'span[data-tooltip*="Cc"]',
                    'div[data-tooltip*="Cc"]',
                    'span:has-text("Cc")',
                    'div:has-text("Cc")',
                    '.aB.gQ.pE'  # Gmail CC button class
                ]
                
                cc_added = False
                for cc_button_selector in cc_button_selectors:
                    try:
                        await page.wait_for_selector(cc_button_selector, timeout=3000)
                        await page.click(cc_button_selector)
                        await page.wait_for_timeout(1000)
                        
                        # Try different CC input selectors
                        cc_input_selectors = [
                            'input[peoplekit-id="dlgBr"]',
                            'textarea[name="cc"]',
                            'input[name="cc"]',
                            'div[data-name="cc"] input'
                        ]
                        
                        for cc_input_selector in cc_input_selectors:
                            try:
                                await page.wait_for_selector(cc_input_selector, timeout=3000)
                                all_cc_emails = ", ".join(self.cc_emails)
                                await page.fill(cc_input_selector, all_cc_emails)
                                await page.keyboard.press('Tab')
                                print(f"Added CC recipients: {all_cc_emails}")
                                cc_added = True
                                break
                            except:
                                continue
                        
                        if cc_added:
                            break
                            
                    except:
                        continue
                
                if not cc_added:
                    print("Could not add CC recipients (continuing without CC)")
                    
            except Exception as e:
                print(f"CC addition failed (continuing): {e}")
            
            # Fill Subject
            print("Adding subject...")
            subject_selectors = [
                'input[name="subjectbox"]',
                'input[placeholder*="Subject"]',
                'input[aria-label*="Subject"]'
            ]
            
            subject_added = False
            for subject_selector in subject_selectors:
                try:
                    await page.wait_for_selector(subject_selector, timeout=5000)
                    await page.fill(subject_selector, subject)
                    print("Subject added")
                    subject_added = True
                    break
                except:
                    continue
            
            if not subject_added:
                print("Could not find subject field")
                return False
            
            # Fill Body
            print("Adding email body...")
            body_selectors = [
                'div[contenteditable="true"][role="textbox"]',
                'div[contenteditable="true"]',
                'div[aria-label*="Message"]',
                'div.Am.Al.editable'
            ]
            
            body_added = False
            for body_selector in body_selectors:
                try:
                    await page.wait_for_selector(body_selector, timeout=5000)
                    await page.click(body_selector)
                    await page.fill(body_selector, body)
                    print("Email body added")
                    body_added = True
                    break
                except:
                    continue
            
            if not body_added:
                print("Could not find body field")
                return False
            
            # Wait before sending
            await page.wait_for_timeout(2000)
            
            # Send email
            print("Sending email...")
            send_selectors = [
                'div[data-tooltip*="Send"]',
                'div[aria-label*="Send"]',
                'div.T-I.T-I-KE.L3:has-text("Send")',
                'button:has-text("Send")',
                'div[role="button"]:has-text("Send")'
            ]
            
            email_sent = False
            for send_selector in send_selectors:
                try:
                    await page.wait_for_selector(send_selector, timeout=5000)
                    await page.click(send_selector)
                    print("Send button clicked")
                    email_sent = True
                    break
                except:
                    continue
            
            if not email_sent:
                # Try keyboard shortcut as fallback
                print("Trying keyboard shortcut Ctrl+Enter...")
                await page.keyboard.press('Control+Enter')
                email_sent = True
            
            # Wait for email to send
            await page.wait_for_timeout(3000)
            
            if email_sent:
                print(f"Email sent successfully for {name} ({phone_number})")
                return True
            else:
                print(f"Could not send email for {name}")
                return False
            
        except Exception as e:
            print(f"Error sending email for {name}: {str(e)}")
            # Try to close compose window if open
            try:
                await page.keyboard.press('Escape')
                await page.wait_for_timeout(1000)
            except:
                pass
            return False
    
    async def process_csv_and_send_emails(self, csv_file_path, delay_seconds=10):
        """Read CSV and send emails through Gmail"""
        async with async_playwright() as p:
            # Launch browser (set headless=False to see the browser)
            browser = await p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
            context = await browser.new_context()
            page = await context.new_page()
            
            try:
                # Try to load previous session
                session_loaded = await self.load_session(context)
                if session_loaded:
                    print("Attempting to use saved session...")
                
                # Login to Gmail
                if not await self.login_to_gmail(page, context):
                    print("Failed to login to Gmail")
                    return
                
                # Confirm ready to start sending emails
                print("\n" + "="*60)
                print("READY TO START EMAIL CAMPAIGN")
                print("="*60)
                print(f"CSV file: {csv_file_path}")
                print(f"From: {self.sender_email}")
                print(f"To: {', '.join(self.to_emails)}")
                print(f"CC: {', '.join(self.cc_emails)}")
                print(f"Delay: {delay_seconds} seconds between emails")
                
                self.wait_for_user_confirmation("Ready to start sending emails?")
                
                # Process CSV file
                print(f"Reading CSV file: {csv_file_path}")
                
                with open(csv_file_path, 'r', encoding='utf-8-sig') as csvfile:
                    reader = csv.DictReader(csvfile)
                    
                    print(f"CSV Headers found: {reader.fieldnames}")
                    print("="*50)
                    
                    total_rows = 0
                    successful_sends = 0
                    failed_sends = 0
                    
                    for row_number, row in enumerate(reader, 1):
                        total_rows += 1
                        
                        # Extract name and phone
                        name = row.get('Name', '').strip()
                        phone = row.get('Mobile', '').strip()
                        
                        if not name or not phone:
                            print(f"Row {row_number}: Missing name or phone number. Skipping...")
                            failed_sends += 1
                            continue
                        
                        print(f"\nProcessing Row {row_number}: {name} - {phone}")
                        
                        # Send email
                        if await self.compose_and_send_email(page, name, phone, row_number):
                            successful_sends += 1
                        else:
                            failed_sends += 1
                        
                        # Wait before next email (except for last email)
                        if row_number < total_rows:
                            print(f"Waiting {delay_seconds} seconds before next email...")
                            await page.wait_for_timeout(delay_seconds * 1000)
                    
                    # Summary
                    print("\n" + "=" * 50)
                    print("EMAIL CAMPAIGN SUMMARY")
                    print("=" * 50)
                    print(f"Total rows processed: {total_rows}")
                    print(f"Emails sent successfully: {successful_sends}")
                    print(f"Failed sends: {failed_sends}")
                    print(f"Success rate: {(successful_sends/total_rows*100):.1f}%" if total_rows > 0 else "0%")
                    print("=" * 50)
                
                # Keep browser open for review
                self.wait_for_user_confirmation("All emails processed! Press Enter to close browser")
                
            except FileNotFoundError:
                print(f"Error: CSV file not found at {csv_file_path}")
            except Exception as e:
                print(f"Error: {str(e)}")
                import traceback
                traceback.print_exc()
            finally:
                # Safe browser close with error handling
                try:
                    if not browser.is_connected():
                        print("Browser already disconnected")
                    else:
                        print("Closing browser...")
                        await browser.close()
                except Exception as e:
                    print(f"Browser close error (can be ignored): {e}")
                    pass

async def main():
    # Configuration
    CSV_FILE_PATH = r"C:\Users\khush\email canvas home\leads-canvashome.csv"
    DELAY_BETWEEN_EMAILS = 3  # seconds (Much faster - reduced from 5 to 3)
    
    # Create email sender
    gmail_sender = GmailEmailSender()
    
    print("Gmail Automation Configuration:")
    print(f"From: {gmail_sender.sender_email}")
    print(f"To: {', '.join(gmail_sender.to_emails)}")
    print(f"CC: {', '.join(gmail_sender.cc_emails)}")
    print(f"Delay between emails: {DELAY_BETWEEN_EMAILS} seconds")
    print("="*70)
    
    # Start the automation
    await gmail_sender.process_csv_and_send_emails(CSV_FILE_PATH, DELAY_BETWEEN_EMAILS)

if __name__ == "__main__":
    asyncio.run(main())