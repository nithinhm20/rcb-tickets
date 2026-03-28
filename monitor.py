"""
RCB Ticket Monitor — GitHub Actions / Cloud version
- Detects ALL matches with a BUY TICKETS button
- Uses specific HTML classes (chakra-text) to extract team names
- Handles multiple matches appearing simultaneously
"""

import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formatdate, make_msgid
from playwright.sync_api import sync_playwright

URL                 = "https://shop.royalchallengers.com/ticket"

SENDER_EMAIL        = os.environ["ZOHO_ADDRESS"]
SENDER_APP_PASSWORD = os.environ["ZOHO_APP_PASSWORD"]

# List containing both email addresses
RECIPIENT_EMAILS    = [
    os.environ["ZOHO_ADDRESS"],
    os.environ["OUTLOOK_ADDRESS"]
]


def get_live_matches() -> list[dict]:
    matches = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-dev-shm-usage",
            ]
        )

        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            java_script_enabled=True,
            extra_http_headers={
                "Accept-Language": "en-IN,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            }
        )

        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en'] });
            window.chrome = { runtime: {} };
        """)

        page = context.new_page()

        print("Loading page...")
        page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(5000)
        page.evaluate("window.scrollBy(0, 300)")
        page.wait_for_timeout(2000)

        try:
            buttons = page.locator("button.chakra-button").all()
            print(f"Found {len(buttons)} chakra buttons total")

            for btn in buttons:
                try:
                    text = btn.inner_text().strip().upper()
                    if "BUY TICKETS" not in text:
                        continue

                    # Execute JavaScript to find the specific card and extract the chakra-text <p> tags
                    match_data = page.evaluate("""(btn) => {
                        let card = btn;
                        
                        // 1. Walk up the DOM to find the main container card for THIS specific button
                        for (let i = 0; i < 15; i++) {
                            if (!card.parentElement) break;
                            card = card.parentElement;
                            if (card.innerText && (card.innerText.includes('VS') || card.innerText.includes('vs'))) {
                                break; // We found the match card boundary
                            }
                        }

                        // 2. Find all <p class="chakra-text"> inside this specific card
                        // This uses your discovery but protects against changing CSS hashes
                        let pElements = Array.from(card.querySelectorAll('p.chakra-text'));
                        let texts = pElements.map(p => p.innerText.trim()).filter(t => t.length > 0);

                        // 3. Filter out noise to isolate the team names
                        let teams = texts.filter(t => 
                            t.toUpperCase() !== 'VS' && 
                            !t.includes('202') && 
                            !t.includes('PM') && 
                            !t.includes('AM') &&
                            !t.includes('₹') && 
                            !t.includes('Rs')
                        );

                        // 4. Grab the date directly from the card's full text
                        let allLines = card.innerText.split('\\n').map(l => l.trim()).filter(l => l);
                        let dateLine = allLines.find(l => l.includes('202') || l.includes(' PM') || l.includes(' AM')) || "Unknown Date";

                        return {
                            teams: teams,
                            date: dateLine
                        };
                    }""", btn.element_handle())

                    if match_data:
                        teams = match_data.get("teams", [])
                        date = match_data.get("date", "Unknown date")

                        # Format the matchup based on what we found in the <p> tags
                        if len(teams) >= 2:
                            # Grabs the first two valid team names it found
                            opponent = f"{teams[0]} vs {teams[1]}" 
                        elif len(teams) == 1:
                            opponent = teams[0]
                        else:
                            opponent = "Unknown Match"

                        key = f"{opponent} {date}".replace(" ", "_")
                        
                        matches.append({
                            "key":      key,
                            "opponent": opponent,
                            "date":     date
                        })

                        print(f"  ✅ BUY TICKETS found — {opponent} | {date}")

                except Exception as e:
                    print(f"  Error reading button details: {e}")
                    continue

        except Exception as e:
            print(f"Button search error: {e}")

        browser.close()

    return matches


def send_email(live_matches: list[dict]):
    match_lines = ""
    for m in live_matches:
        match_lines += f"\n🏏 {m['opponent']}\n   📅 {m['date']}\n   👉 {URL}\n"

    subject = f"🚨 RCB Tickets Live — {len(live_matches)} match(es) available!"
    body = f"""Great news! BUY TICKETS is currently available for the following RCB match(es):

{match_lines}
Act fast — tickets sell out quickly!

— Your RCB Ticket Monitor
"""
    msg = MIMEMultipart()
    msg["From"]       = SENDER_EMAIL
    msg["To"]         = ", ".join(RECIPIENT_EMAILS)
    msg["Subject"]    = subject
    
    msg["Date"]       = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="zohomail.in")
    
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.zoho.in", 465) as server:
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECIPIENT_EMAILS, msg.as_string())
        print(f"✅ Zoho email sent successfully to: {', '.join(RECIPIENT_EMAILS)}")
    except Exception as e:
        print(f"❌ Failed to send email via Zoho: {e}")


if __name__ == "__main__":
    print(f"Checking: {URL}")

    live_matches = get_live_matches()

    if live_matches:
        print(f"🎉 {len(live_matches)} match(es) with BUY TICKETS found — sending email!")
        send_email(live_matches)
    else:
        print("⏳ No BUY TICKETS button yet. Will check again next run.")

    sys.exit(0)
