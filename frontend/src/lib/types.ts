/** Domain types mirroring backend/app/schemas (snake_case, as returned by the API). */

export type Role = "hospital_user" | "bloodbank_user" | "admin" | "auditor";

export type BloodGroup = "A+" | "A-" | "B+" | "B-" | "AB+" | "AB-" | "O+" | "O-";

export type ComponentType = "WHOLE_BLOOD" | "RBC";

export type StockoutRisk =
  | "IMMEDIATE_EMPTY"
  | "CRITICAL"
  | "HIGH"
  | "MODERATE"
  | "STABLE"
  | "EXPIRES_BEFORE_USE";

export type RequestStatus =
  | "OPEN"
  | "HELD"
  | "CONFIRMED"
  | "CANCELLED"
  | "EXPIRED"
  | "FULFILLED";

export interface User {
  id: string;
  username: string;
  email: string;
  role: Role;
  affiliated_org_id: string | null;
  is_active: boolean;
  created_at: string | null;
  last_login: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface UsageStat {
  blood_group: BloodGroup;
  component_type: ComponentType;
  total_requests: number;
  total_units_consumed: number;
  observation_days: number;
  avg_usage_per_day: number;
  weekly_usage: number;
  hourly_burn_rate: number;
  peak_24h_demand: number;
  recent_trend: string;
}

export interface Depletion {
  blood_bank_id: string;
  blood_bank_code: string;
  blood_bank_name: string;
  blood_group: BloodGroup;
  component_type: ComponentType;
  units_available: number;
  units_reserved: number;
  units_unreserved: number;
  avg_usage_per_day: number;
  weekly_usage: number;
  hours_until_depletion: number;
  days_until_depletion: number;
  predicted_depletion_timestamp: string;
  stockout_risk: StockoutRisk;
  confidence_interval_hours: [number, number];
  earliest_batch_expiry: string | null;
  depletion_cause: string;
  model_source: string | null;
}

export interface ForecastSummary {
  generated_at: string;
  ml_model_loaded: boolean;
  model_path: string | null;
  total_inventory_items_monitored: number;
  critical_stockouts_count: number;
  high_risk_stockouts_count: number;
  usage_statistics: UsageStat[];
  depletion_predictions: Depletion[];
}

export interface InventoryItem {
  id: string;
  code: string;
  blood_bank_id: string;
  blood_group: BloodGroup;
  component_type: ComponentType;
  units_available: number;
  units_reserved: number;
  collection_date: string;
  expiry_date: string;
  storage_location_code: string | null;
  is_available: boolean;
  last_updated: string;
}

export interface Match {
  inventory_id: string;
  inventory_code: string;
  blood_bank_id: string;
  blood_bank_name: string;
  blood_group: BloodGroup;
  component_type: ComponentType;
  expiry_date: string;
  units_available: number;
  units_reserved: number;
  ranking: number;
  match_score: number;
  distance_km: number;
  eta_minutes: number;
  explanation: string;
}

export interface BloodRequest {
  id: string;
  code: string;
  hospital_id: string;
  blood_group: BloodGroup;
  component_type: ComponentType;
  quantity_units: number;
  urgency: number;
  status: RequestStatus;
  shortage_type: string | null;
  priority_score: number | null;
  required_by_timestamp: string | null;
  request_timestamp: string;
  created_by_user_id: string;
  matches: Match[];
}

export interface Alert {
  id: string;
  request_id: string | null;
  alert_type: string;
  message: string;
  recipient_user_id: string;
  is_read: boolean;
  created_at: string;
  read_at: string | null;
}

export interface Reservation {
  id: string;
  request_id: string;
  inventory_id: string;
  quantity: number;
  status: string;
  expires_at: string;
  created_at: string;
  updated_at: string;
}

export interface RequestCreate {
  blood_group: BloodGroup;
  component_type: ComponentType;
  quantity_units: number;
  urgency: number;
  required_by_timestamp?: string | null;
}

export interface InventoryCreate {
  blood_bank_id?: string | null;
  blood_group: BloodGroup;
  component_type: ComponentType;
  units_available: number;
  collection_date: string;
  expiry_date: string;
  storage_location_code?: string | null;
}

/* ---- eRaktKosh live stock (scraped from MoHFW / C-DAC) ---- */

export interface EraktkoshGroupSummary {
  key: string;
  total_units: number;
  unique_banks: number;
  record_count: number;
  file_json: string;
  file_csv: string;
}

export interface EraktkoshSummary {
  last_updated: string;
  last_updated_iso: string;
  total_records_scanned: number;
  blood_groups: Record<string, EraktkoshGroupSummary>;
}

export interface EraktkoshBankRecord {
  blood_bank_name: string;
  category: string;
  district: string;
  component: string;
  units: number;
  phone: string;
  email: string;
  address: string;
  last_updated: string;
  type: string;
  all_groups: Record<string, number>;
}

export interface EraktkoshBangalorePayload {
  blood_group: string;
  key: string;
  city: string;
  last_updated: string;
  last_updated_iso: string;
  total_units: number;
  unique_banks: number;
  record_count: number;
  data: EraktkoshBankRecord[];
}

/* One row per real blood bank, as returned by GET /eraktkosh/supply. */
export interface EraktkoshSupply {
  name: string;
  address: string;
  phone: string;
  email: string;
  category: string;
  all_groups: Record<string, number>;
  last_updated: string;
}
