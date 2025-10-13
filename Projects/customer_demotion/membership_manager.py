import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
import google.generativeai as genai
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configure Gemini API
GOOGLE_API_KEY = 'YOUR GEMINI API KEY'  # Replace with your actual Gemini API key
genai.configure(api_key=GOOGLE_API_KEY)

# Email configuration
EMAIL_ADDRESS = "your-email@gmail.com"  # Replace with your email
EMAIL_PASSWORD = "your-app-specific-password"  # Replace with your password

# Database connection function
def get_database_connection():
    password = quote_plus('YOUR DATABASE PASSWORD')
    engine = create_engine(f'postgresql+pg8000://postgres:{password}@localhost:5432/sales_db')
    return engine

# [Insert the new tier level and discount functions here]
def get_tier_level(tier):
    """Get numerical level for membership tier comparison"""
    tiers = {
        'Bronze': 1,
        'Silver': 2,
        'Gold': 3,
        'Platinum': 4
    }
    return tiers.get(tier, 0)

def get_category_discounts(tier):
    """Get standard discount rates based on membership tier"""
    discounts = {
        'Bronze': 5,
        'Silver': 10,
        'Gold': 15,
        'Platinum': 20
    }
    return discounts.get(tier, 0)
# [Insert the customer data function here]
def get_customer_data(customer_id, engine):
    """Fetch detailed customer data including location, browsing and purchase history"""
    query = text("""
        SELECT 
            sd."CustomerID",
            sd."Name",
            sd."Email",
            sd."Location",
            sd."MembershipTier",
            -- Get last 5 purchases
            (SELECT json_agg(p) FROM (
                SELECT "ProductName", "PurchaseDate", "Amount"
                FROM sales_data 
                WHERE "CustomerID" = sd."CustomerID"
                ORDER BY "PurchaseDate" DESC 
                LIMIT 5
            ) p) as recent_purchases,
            -- Get browsing history
            (SELECT json_agg(b) FROM (
                SELECT "ProductCategory", "VisitDate"
                FROM browsing_history 
                WHERE "CustomerID" = sd."CustomerID"
                ORDER BY "VisitDate" DESC 
                LIMIT 5
            ) b) as browsing_history
        FROM sales_data sd
        WHERE sd."CustomerID" = :customer_id
        LIMIT 1
    """)
    try:
        with engine.connect() as conn:
            result = conn.execute(query, {"customer_id": customer_id})
            data = result.fetchone()
            if data:
                return {
                    'CustomerID': data[0],
                    'Name': data[1],
                    'Email': data[2],
                    'Location': data[3],
                    'MembershipTier': data[4],
                    'recent_purchases': data[5] if data[5] else [],
                    'browsing_history': data[6] if data[6] else []
                }
            return None
    except Exception as e:
        st.error(f"Error fetching customer data: {str(e)}")
        return None
# [Insert the email generation function here]
def generate_email_content(customer_data, new_tier):
    """Generate personalized email content using Gemini based on tier change"""
    
    # Determine if this is a promotion or demotion
    current_tier_level = get_tier_level(customer_data['MembershipTier'])
    new_tier_level = get_tier_level(new_tier)
    is_promotion = new_tier_level > current_tier_level
    
    # Get standard discount for new tier
    base_discount = get_category_discounts(new_tier)
    # Add extra discount for demotion case
    compensation_discount = 10 if not is_promotion else 0
    total_discount = base_discount + compensation_discount

    prompt = f"""
    Create a personalized email for a customer whose membership tier has been {
    'upgraded' if is_promotion else 'changed'} from {customer_data['MembershipTier']} to {new_tier}.

    Customer Details:
    - Name: {customer_data['Name']}
    - Location: {customer_data['Location']}
    - Recent Purchases: {customer_data['recent_purchases']}
    - Browsing History: {customer_data['browsing_history']}
    
    Scenario: {'PROMOTION' if is_promotion else 'TIER CHANGE'}
    Discount Available: {total_discount}% off on their preferred categories
    
    Requirements:
    1. {'Express excitement about their promotion and new benefits' if is_promotion 
        else 'Be empathetic and focus on the special offers to retain their interest'}
    2. Reference their location and shopping patterns
    3. {'Highlight the expanded benefits of their new tier' if is_promotion 
        else 'Emphasize the special retention offers and benefits'}
    4. Include personalized recommendations based on their browsing/purchase history
    5. {'Congratulatory tone' if is_promotion 
        else 'Encouraging tone with focus on special offers'}
    6. Mention the {total_discount}% discount specifically for their frequently browsed categories
    7. Keep it concise (max 200 words)
    8. Make sure to include the discount percentage in the email
    9. Make sure to include the discount percentage in the subject line
    10. Make sure to change the tone as per the demographics of the customer
    
    Additional Instructions:
    {'''
    - Be celebratory
    - Highlight premium status
    - Mention exclusive new benefits
    - Include VIP treatment references
    ''' if is_promotion else '''
    - Focus on special retention offers
    - Emphasize the extra 10% bonus discount
    - Highlight membership value
    - Include personalized comeback incentives
    '''}
    
    Format the response exactly as follows:
    Subject Line: [Your subject line here]
    Email Body: [Your email body here]
    """
    
    try:
        # Initialize Gemini model
        model = genai.GenerativeModel('gemini-pro')
        
        # Generate response
        response = model.generate_content(prompt)
        
        # Extract subject and body from response
        content = response.text
        
        # Split into subject and body
        parts = content.split('Email Body:')
        subject_line = parts[0].replace('Subject Line:', '').strip()
        email_body = parts[1].strip() if len(parts) > 1 else ''
        
        # Print email content to console
        print("\n" + "="*50)
        print("GENERATED EMAIL CONTENT")
        print("="*50)
        print(f"To: {customer_data['Email']}")
        print(f"Subject: {subject_line}")
        print("-"*50)
        print("Body:")
        print(email_body)
        print("="*50 + "\n")
        
        return subject_line, email_body
    except Exception as e:
        print(f"Error generating email content: {str(e)}")
        return None, None

# [Insert the email sending function here]
def send_email(to_email, subject, body):
    """Send email using SMTP"""
    try:
        # Create message container
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Add body to email
        msg.attach(MIMEText(body, 'plain'))
        
        # Create SMTP session
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()  # Enable TLS
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            
            # Convert message to string and send
            text = msg.as_string()
            server.sendmail(EMAIL_ADDRESS, to_email, text)
            
        return True
    except Exception as e:
        st.error(f"Error sending email: {str(e)}")
        return False

# Function to update membership tier
def update_membership(customer_id, new_tier):
    engine = get_database_connection()
    try:
        # Get current tier before update
        current_tier_query = text("""
            SELECT "MembershipTier" FROM sales_data 
            WHERE "CustomerID" = :customer_id LIMIT 1
        """)
        with engine.connect() as conn:
            current_tier = conn.execute(current_tier_query, 
                {"customer_id": customer_id}).scalar()
        
        # Update database
        with engine.connect() as conn:
            query = text("""
                UPDATE sales_data 
                SET "MembershipTier" = :new_tier 
                WHERE "CustomerID" = :customer_id
            """)
            conn.execute(query, {"new_tier": new_tier, "customer_id": customer_id})
            conn.commit()
        
        # Get detailed customer data
        customer_data = get_customer_data(customer_id, engine)
        
        if customer_data:
            # Store original tier in customer_data for email generation
            customer_data['MembershipTier'] = current_tier
            
            # Generate email content
            subject, body = generate_email_content(customer_data, new_tier)
            
            if subject and body:
                # Send email
                if send_email(customer_data['Email'], subject, body):
                    is_promotion = get_tier_level(new_tier) > get_tier_level(current_tier)
                    message = ("Membership upgraded" if is_promotion else "Membership updated") + \
                             " and notification email sent!"
                    st.success(message)
                else:
                    st.warning("Membership updated but failed to send email.")
            else:
                st.warning("Membership updated but failed to generate email content.")
        
        return True
    except Exception as e:
        st.error(f"Error updating membership: {str(e)}")
        return False



# Function to load all customers
def load_customers():
    engine = get_database_connection()
    query = """
    SELECT DISTINCT "CustomerID", "Name", "Email", "MembershipTier"
    FROM sales_data
    ORDER BY "Name"
    """
    return pd.read_sql(query, engine)

# Streamlit UI
# Initialize session state
if 'page' not in st.session_state:
    st.session_state.page = 'Membership Manager'

# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Go to",
    ["Membership Manager", "Customer Overview"]
)
st.session_state.page = page

# Function to create page header
def page_header(title, description=""):
    st.title(title)
    if description:
        st.markdown(description)
    st.divider()

def membership_manager_page():
    page_header("Membership Manager", "Update customer membership tiers and send notifications")
    
    # Create two columns with better proportions
    col1, col2 = st.columns([2, 3])
    
    # Load customers
    customers_df = load_customers()
    customers_df['display_name'] = customers_df.apply(
        lambda x: f"{x['Name']} ({x['Email']})", axis=1
    )
    
    with col1:
        st.subheader("Select Customer")
        selected_customer = st.selectbox(
            "Choose a customer",
            options=customers_df['display_name'].unique(),
            key='customer_select',
            help="Type to search for a customer"
        )
        
        selected_customer_data = customers_df[
            customers_df['display_name'] == selected_customer
        ].iloc[0]
        
        st.markdown("### Current Details")
        st.markdown(f"""
        **Customer ID:** {selected_customer_data['CustomerID']}  
        **Name:** {selected_customer_data['Name']}  
        **Email:** {selected_customer_data['Email']}  
        **Current Tier:** {selected_customer_data['MembershipTier']}
        """)
        
        new_tier = st.selectbox(
            "Select new membership tier",
            options=['Bronze', 'Silver', 'Gold', 'Platinum'],
            index=['Bronze', 'Silver', 'Gold', 'Platinum'].index(selected_customer_data['MembershipTier'])
        )
        
        if st.button("Update Membership", key="update_btn", type="primary"):
            if new_tier != selected_customer_data['MembershipTier']:
                with st.spinner("Updating membership..."):
                    if update_membership(selected_customer_data['CustomerID'], new_tier):
                        st.success("✅ Membership updated successfully!")
                        st.rerun()
            else:
                st.info("No change in membership tier")


def customer_overview_page():
    page_header("Customer Overview", "View and analyze customer data")
    
    # Load and display customer data
    customers_df = load_customers()
    
    # Add metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Customers", len(customers_df))
    with col2:
        st.metric("Platinum Members", len(customers_df[customers_df['MembershipTier'] == 'Platinum']))
    with col3:
        st.metric("Gold Members", len(customers_df[customers_df['MembershipTier'] == 'Gold']))
    with col4:
        st.metric("Silver Members", len(customers_df[customers_df['MembershipTier'] == 'Silver']))
    with col5:
        st.metric("Bronze Members", len(customers_df[customers_df['MembershipTier'] == 'Bronze']))
    
    # Display customer table with filters
    st.subheader("Customer Database")
    
    # Add filters
    col1, col2 = st.columns(2)
    with col1:
        tier_filter = st.multiselect(
            "Filter by Tier",
            options=['Bronze', 'Silver', 'Gold', 'Platinum'],
            default=[]
        )
    
    with col2:
        search = st.text_input("Search by Name or Email", "")
    
    # Apply filters
    filtered_df = customers_df.copy()
    if tier_filter:
        filtered_df = filtered_df[filtered_df['MembershipTier'].isin(tier_filter)]
    if search:
        filtered_df = filtered_df[
            filtered_df['Name'].str.contains(search, case=False) |
            filtered_df['Email'].str.contains(search, case=False)
        ]
    
    # Display filtered table
    st.dataframe(
        filtered_df[['Name', 'Email', 'MembershipTier', 'CustomerID']],
        hide_index=True,
        use_container_width=True
    )

def main():
    # Apply custom CSS
    st.markdown("""
        <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        .stButton>button {
            width: 100%;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Route to appropriate page
    if st.session_state.page == "Membership Manager":
        membership_manager_page()
    else:
        customer_overview_page()

if __name__ == "__main__":
    main()
