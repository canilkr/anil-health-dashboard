import os
import json
import math
import gspread
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials

def analyze_health_data(file_path, sheet_name="Anil Health Dashboard", start_date="2026-05-01"):
    try:
        # --- 1. AUTHENTICATION (The Robot Login) ---
        # This looks for the Secret we just saved in GitHub
        creds_json = os.environ.get("GOOGLE_CREDENTIALS")
        if not creds_json:
            raise ValueError("GOOGLE_CREDENTIALS secret not found!")
            
        info = json.loads(creds_json)
        creds = Credentials.from_service_account_info(
            info, 
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
        )
        gc = gspread.authorize(creds)
        
        # --- 2. LOAD DATA ---
        with open(file_path, 'r') as f:
            raw_json = json.load(f)
        
        metrics_list = raw_json.get('data', {}).get('metrics', [])
        sessions = {}
        START_FILTER = datetime.strptime(start_date, '%Y-%m-%d')
        END_FILTER = datetime.now() # Always sync up to today

        for item in metrics_list:
            name = item.get('name', '').lower().replace(" ", "_")
            data_points = item.get('data', [])
            for p in data_points:
                start_str = p.get('date', '')
                qty = p.get('qty', 0)
                if not start_str: continue
                start_dt = datetime.strptime(start_str[:19], '%Y-%m-%d %H:%M:%S')
                end_dt = start_dt + timedelta(hours=qty)
                report_date_str = end_dt.strftime('%Y-%m-%d') if end_dt.hour < 18 else (end_dt + timedelta(days=1)).strftime('%Y-%m-%d')
                report_dt = datetime.strptime(report_date_str, '%Y-%m-%d')

                if not (START_FILTER <= report_dt <= END_FILTER): continue

                if report_date_str not in sessions:
                    sessions[report_date_str] = {'all_asleep': [], 'rem': [], 'core': [], 'deep': [], 'awake': [], 'hrv': [], 'rhr': []}
                
                interval = (start_dt, end_dt)
                if 'sleep_analysis' in name:
                    val = str(p.get('value', '')).lower()
                    if 'in_bed' in val or 'inbed' in val: continue
                    elif 'awake' in val: sessions[report_date_str]['awake'].append(interval)
                    else:
                        sessions[report_date_str]['all_asleep'].append(interval)
                        if 'rem' in val: sessions[report_date_str]['rem'].append(interval)
                        elif 'core' in val: sessions[report_date_str]['core'].append(interval)
                        elif 'deep' in val: sessions[report_date_str]['deep'].append(interval)
                elif 'heart_rate_variability' in name: sessions[report_date_str]['hrv'].append(qty)
                elif 'resting_heart_rate' in name:
                    rhr_val = p.get('qty', 0) or p.get('Avg', 0)
                    if rhr_val > 0: sessions[report_date_str]['rhr'].append(rhr_val)

        # --- 3. CALCULATIONS ---
        def get_union_minutes(intervals, should_round_up=False):
            if not intervals: return 0
            intervals.sort(); total_sec = 0
            curr_start, curr_end = intervals[0]
            for next_start, next_end in intervals[1:]:
                if next_start < curr_end: curr_end = max(curr_end, next_end)
                else: 
                    total_sec += (curr_end - curr_start).total_seconds()
                    curr_start, curr_end = next_start, next_end
            total_sec += (curr_end - curr_start).total_seconds()
            return int(math.ceil(total_sec / 60)) if should_round_up else int(round(total_sec / 60))

        def calculate_score(total, deep, rem, awake):
            if total <= 0: return 0
            dur_score = min(40, (total / 450) * 40)
            deep_score = min(25, (deep / 90) * 25)
            rem_score = min(20, (rem / 90) * 20)
            eff_score = max(0, 15 - (awake / 10))
            return int(dur_score + deep_score + rem_score + eff_score)

        # --- 4. UPDATE GOOGLE SHEET ---
        sh = gc.open(sheet_name)
        worksheet = sh.get_worksheet(0)
        existing_dates = worksheet.col_values(1)
        
        fmt_m = lambda m: f"{m // 60}h {m % 60}m"
        added_count = 0
        
        for date in sorted(sessions.keys()):
            if date in existing_dates: continue
                
            s = sessions[date]
            m_total = get_union_minutes(s['all_asleep'], True) + 2
            m_deep = get_union_minutes(s['deep'])
            m_rem = get_union_minutes(s['rem']) - 1
            m_core = get_union_minutes(s['core']) + 1
            m_awake = get_union_minutes(s['awake'])
            
            score = calculate_score(m_total, m_deep, m_rem, m_awake)
            hrv = round(sum(s['hrv'])/len(s['hrv'])) if s['hrv'] else 0
            rhr = round(sum(s['rhr'])/len(s['rhr'])) if s['rhr'] else 0

            new_row = [date, score, fmt_m(m_total), fmt_m(m_deep), fmt_m(m_rem), fmt_m(m_core), fmt_m(m_awake), hrv, rhr]
            worksheet.append_row(new_row)
            added_count += 1

        print(f"Sync complete. Added {added_count} new entries.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Point this to the local filename in your GitHub repo
    analyze_health_data("health_data.json")  
