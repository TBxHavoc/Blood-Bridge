#!/usr/bin/env python3
"""
eRaktKosh Scraper for Bangalore (O+ve and all blood groups) using Scrapling.
Source: https://eraktkosh.mohfw.gov.in/eraktkoshPortal/#/
API Endpoint: https://eraktkosh.mohfw.gov.in/BLDAHIMS/bloodbank/nearbyBB.cnt
"""

import csv
import json
import os
import re
from datetime import datetime
from scrapling import Fetcher

COMPONENTS = {
    11: "Whole Blood",
    12: "Packed Red Blood Cells",
    13: "Fresh Frozen Plasma",
    14: "Single Donor Platelet",
    16: "Platelet Rich Plasma",
    17: "Cryoprecipitate",
    18: "Single Donor Plasma",
    19: "Plasma",
    20: "Platelet Concentrate",
    21: "Cryo Poor Plasma",
    23: "Random Donor Platelets",
    28: "Sagm Packed Red Blood Cells",
    29: "Irradiated RBC",
    30: "Leukoreduced Rbc"
}

DISTRICTS = {
    572: "Bangalore Urban",
    583: "Bangalore Rural"
}

def clean_json_str(text: str) -> str:
    out = []
    in_string = False
    escaped = False
    for char in text:
        if in_string:
            if escaped:
                out.append(char)
                escaped = False
                continue
            if char == '\\':
                out.append(char)
                escaped = True
                continue
            if char == '"':
                out.append(char)
                in_string = False
                continue
            code = ord(char)
            if code < 0x20:
                if code == 0x0a:
                    out.append('\\n')
                elif code == 0x0d:
                    out.append('\\r')
                elif code == 0x09:
                    out.append('\\t')
                else:
                    out.append(f'\\u{code:04x}')
                continue
            out.append(char)
            continue
        if char == '"':
            in_string = True
        out.append(char)
    return "".join(out)

def strip_tags(text: str) -> str:
    text = re.sub(r'<br\s*/?>', ' | ', text, flags=re.I)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;', ' ', text, flags=re.I)
    text = re.sub(r'&amp;', '&', text, flags=re.I)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def parse_contact(contact_raw: str):
    parts = [p.strip() for p in contact_raw.split('<br/>') if p.strip()]
    name = parts[0] if len(parts) > 0 else ""
    address = parts[1] if len(parts) > 1 else ""
    contact_info = parts[2] if len(parts) > 2 else ""
    
    phone, email, fax = "", "", ""
    m_phone = re.search(r'Phone:\s*([^,]+)', contact_info, re.I)
    if m_phone:
        p = m_phone.group(1).strip()
        if p not in ['-', 'N/A', 'NA']: phone = p
        
    m_fax = re.search(r'Fax:\s*([^,]+)', contact_info, re.I)
    if m_fax:
        f = m_fax.group(1).strip()
        if f not in ['-', 'N/A', 'NA']: fax = f
        
    m_email = re.search(r'Email:\s*([^\s,]+)', contact_info, re.I)
    if m_email:
        e = m_email.group(1).strip()
        if e not in ['-', 'N/A', 'NA']: email = e

    return {
        "name": name,
        "address": address,
        "phone": phone,
        "fax": fax,
        "email": email
    }

def parse_stock(avail_html: str, target_group="O+"):
    is_available = "Available" in avail_html and "Not Available" not in avail_html
    target_units = 0
    pattern = rf'{re.escape(target_group)}Ve\s*:\s*(\d+)'
    m = re.search(pattern, avail_html, re.I)
    if m:
        target_units = int(m.group(1))
    
    all_groups = {}
    for g_match in re.finditer(r'([A-Za-z0-9+-]+Ve)\s*:\s*(\d+)', avail_html, re.I):
        all_groups[g_match.group(1)] = int(g_match.group(2))
        
    return {
        "is_available": is_available,
        "target_units": target_units,
        "all_groups": all_groups,
        "raw_status": strip_tags(avail_html)
    }

def scrape_bangalore_blood(target_group="O+", output_dir="."):
    print(f"Scraping eRaktKosh for {target_group} blood in Bangalore...")
    records = []
    
    for dist_code, dist_name in DISTRICTS.items():
        for comp_code, comp_name in COMPONENTS.items():
            url = f"https://eraktkosh.mohfw.gov.in/BLDAHIMS/bloodbank/nearbyBB.cnt?hmode=GETNEARBYSTOCKDETAILS&stateCode=29&districtCode={dist_code}&bloodGroup=all&bloodComponent={comp_code}&lang=0"
            try:
                resp = Fetcher.get(url, timeout=20)
                raw = resp.body.decode('utf-8', errors='ignore')
                cleaned = clean_json_str(raw)
                data = json.loads(cleaned)
                rows = data.get("data", [])
                
                for row in rows:
                    if len(row) < 6:
                        continue
                    contact = parse_contact(row[1])
                    if contact["name"] == "-" or not contact["name"]:
                        continue
                        
                    stock = parse_stock(row[3], target_group=target_group)
                    
                    records.append({
                        "district": dist_name,
                        "district_code": dist_code,
                        "component": comp_name,
                        "component_code": comp_code,
                        "blood_bank_name": contact["name"],
                        "address": contact["address"],
                        "category": row[2],
                        "phone": contact["phone"],
                        "email": contact["email"],
                        "fax": contact["fax"],
                        f"{target_group.lower().replace('+', 'pos')}_available": stock["is_available"] and stock["target_units"] > 0,
                        f"{target_group.lower().replace('+', 'pos')}_units": stock["target_units"],
                        "all_available_groups": stock["all_groups"],
                        "status_text": stock["raw_status"],
                        "last_updated": row[4],
                        "type": row[5]
                    })
            except Exception as e:
                print(f"Error fetching {dist_name} component {comp_name}: {e}")

    # Write files
    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, f"bangalore_{target_group.lower().replace('+', 'pos')}_blood_stock.json")
    csv_path = os.path.join(output_dir, f"bangalore_{target_group.lower().replace('+', 'pos')}_blood_stock.csv")
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
        
    matching = [r for r in records if r.get(f"{target_group.lower().replace('+', 'pos')}_units", 0) > 0]
    fieldnames = [
        "blood_bank_name", "category", "district", "component",
        f"{target_group.lower().replace('+', 'pos')}_units", "phone", "email",
        "address", "last_updated", "type"
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in sorted(matching, key=lambda x: x[f"{target_group.lower().replace('+', 'pos')}_units"], reverse=True):
            writer.writerow(r)
            
    print(f"Scraped {len(records)} records. Found {len(matching)} records with active stock.")
    print(f"JSON saved to: {json_path}")
    print(f"CSV saved to: {csv_path}")

if __name__ == "__main__":
    scrape_bangalore_blood("O+")
