import json
import os
import time
from io import BytesIO
import google.generativeai as genai
from dotenv import load_dotenv

# Load API Key
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("❌ GEMINI_API_KEY is missing. Check your .env file.")

genai.configure(api_key=API_KEY)


def upload_to_gemini(file_stream: BytesIO, filename: str = "uploaded.pdf"):
    """Uploads a file-like object to Gemini API (in-memory)."""
    try:
        file = genai.upload_file(
            file_stream,
            mime_type="application/pdf",
            display_name=filename
        )
        print(f"✅ Uploaded file '{filename}' as: {file.uri}")
        return file
    except Exception as e:
        raise ValueError(f"❌ File upload failed: {e}")


def compare_pdfs(file1, file2, doc_type, custom_prompt=None, include_default=False):
    import json

    generation_config = genai.types.GenerationConfig(
        temperature=0.2,  # Lower temperature for more consistent results
        top_p=1,
        top_k=1,
        max_output_tokens=16384,
        response_mime_type="application/json",
    )

    model = genai.GenerativeModel(
        model_name="gemini-1.5-pro",
        generation_config=generation_config,
    )

    results = {}

    # Get default prompt based on document type
    default_prompt = get_default_prompt(doc_type)

    # Process custom prompt if provided
    if custom_prompt and custom_prompt.strip():
        try:
            # Use the custom prompt exactly as entered, but ensure JSON output format
            exact_custom_prompt = f"""
            {custom_prompt.strip()}

            Return ONLY JSON in this exact format:
            {{
                "differences": [
                    {{
                        "field": "Field Name",
                        "file1_value": "Value in first file",
                        "file2_value": "Value in second file"
                    }}
                ]
            }}
            If no differences, return: {{ "differences": [] }}
            """

            chat_session = model.start_chat()
            response = chat_session.send_message([file1, file2, exact_custom_prompt])
            custom_result = json.loads(response.text)
            results["custom"] = custom_result
        except Exception as e:
            results["custom"] = {
                "differences": [],
                "error": f"Custom prompt error: {str(e)}"
            }

    # If include_default is True or no custom prompt provided, process with default prompt
    if include_default or not custom_prompt or not custom_prompt.strip():
        try:
            chat_session = model.start_chat()
            response = chat_session.send_message([file1, file2, default_prompt])
            default_result = json.loads(response.text)
            results["default"] = default_result
        except Exception as e:
            results["default"] = {
                "differences": [],
                "error": f"Default prompt error: {str(e)}"
            }

    # If only one result type exists, return just that result
    if len(results) == 1:
        return json.dumps(list(results.values())[0])

    # Otherwise return both results
    return json.dumps(results)


def get_default_prompt(doc_type):
    """Returns the default prompt based on document type"""
    if doc_type == "Invoices":
        return """
    You are given two invoice documents. Extract and compare the following fields for any mismatches:

    Header-level fields:
    - INVOICE_NO
    - INVOICE_DATE (yyyy-mm-dd)
    - PURCHASE_ORDER
    - SHIPMENT_NUMBER
    - CONTRACT_NUMBER
    - CURRENCY
    - DUE_DATE
    - TOTAL_TAX
    - SUB_TOTAL
    - TOTAL_AMOUNT
    - PAYMENT_TERMS
    - INCOTERMS
    - CARRIER_NAME
    - CARRIER_CODE
    - TRANSPORT_MODE
    - BOOKING_REFERENCE
    - VENDOR_TAX_ID
    - VENDOR_IBAN
    - VENDOR_ZIP
    - VENDOR_CITY
    - VENDOR_NAME
    - CUSTOMER_TAX_ID
    - CUSTOMER_ZIP
    - CUSTOMER_CITY
    - CUSTOMER_NAME
    - CHARGE_AMOUNT
    - DISCOUNT_AMOUNT
    - DELIVERY_ENTITY_TAX_ID
    - DELIVERY_ENTITY_ZIP
    - DELIVERY_ENTITY_CITY
    - DELIVERY_ENTITY_COUNTRY
    - DELIVERY_ENTITY_NAME

    Line item-level fields:
    - LINE_AMOUNT
    - ITEM_DESCRIPTION
    - ITEM_QUANTITY
    - PURCHASE_ORDER
    - WEIGHT_UNIT_OF_MEASUREMENT
    - ITEM_NUMBER
    - EXTERNAL_ITEM_NUMBER
    - UNIT_PRICE
    - HS_CODE
    - CONTAINER_NUMBER
    - CURRENCY
    - CHARGE_AMOUNT
    - DISCOUNT_PERCENTAGE
    - DISCOUNT_AMOUNT
    - TAX_CODE
    - TAX_AMOUNT
    - TAX_PERCENTAGE

    Return the differences as structured JSON in this format:
    {
      "differences": {
        "header_differences": [
          {
            "field": "HEADER_FIELD_NAME",
            "file1_value": "value from file 1",
            "file2_value": "value from file 2"
          }
        ],
        "line_item_differences": [
          {
            "item_index": "1",
            "field": "LINE_ITEM_FIELD_NAME",
            "file1_value": "value from file 1",
            "file2_value": "value from file 2"
          }
        ]
      }
    }

    If there are no mismatches in a category, return an empty array for that category.
    If there are no mismatches at all, return:
    {
      "differences": {
        "header_differences": [],
        "line_item_differences": []
      }
    }
    """
    else:  # For Contracts
        return """
    You are given two contract documents. Carefully read and analyze both.

    Your task is to extract and compare important legal, financial, and administrative fields. Identify and highlight any differences between the two documents.
    
    Focus on the following categories:
    
    General Information:
    - Contract Number, Title, Type
    - Effective Date, Expiration Date, Execution Date, Termination Date
    - Contract Status, Contract Value, Currency, Renewal Terms
    
    Payment & Financial Terms:
    - Payment Terms, Payment Schedule
    - Notice Period, Indemnification Terms, Warranty Terms, Insurance Requirements
    - Limitation of Liability, Intellectual Property Rights
    
    Jurisdiction & Legal Scope:
    - Governing Law, Jurisdiction
    - Termination Conditions, Dispute Resolution Mechanism
    - Compliance Requirements, Force Majeure Clause, Confidentiality Terms
    
    Parties & Contacts:
    - Party 1 and Party 2: Name, Address, Representative, Tax ID, Contact Information
    
    Service & Obligations:
    - Service Level Agreement, Performance Metrics
    - Data Protection, Exclusivity, Non-Compete, Amendment Process
    
    Return only the differences in the following structured JSON format:
    
    ```json
    {
      "differences": [
        {
          "field": "FIELD_NAME",
          "file1_value": "value from contract 1",
          "file2_value": "value from contract 2"
        }
      ]
    }
    """