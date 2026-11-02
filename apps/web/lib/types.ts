export type GenerationStatus = "pending" | "processing" | "completed" | "failed";

export type Me = {
  id: string;
  email: string;
  display_name: string;
  locale: "es" | "en";
  status: string;
  roles: string[];
  created_at: string;
};

export type Balance = { available_credits: number; reserved_credits: number };

export type ProviderModel = {
  model_key: string;
  display_name: string;
  provider: string;
  min_duration_s: number;
  max_duration_s: number;
  credits_per_generation: number;
  supports_seed: boolean;
  supports_negative_prompt: boolean;
  output_format: string;
};

export type Generation = {
  id: string;
  status: GenerationStatus;
  prompt: string;
  negative_prompt: string | null;
  genre: string | null;
  mood: string | null;
  instruments: string[];
  duration_seconds: number;
  seed: number | null;
  reserved_credits: number;
  model_key: string;
  provider: string;
  error_code: string | null;
  error_message: string | null;
  track_id: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
};

export type Track = {
  id: string;
  title: string;
  generation_job_id: string;
  mime_type: string;
  size_bytes: number;
  duration_seconds: number;
  provider: string;
  model_key: string;
  created_at: string;
};

export type LedgerEntry = {
  id: string;
  kind: string;
  available_delta: number;
  reserved_delta: number;
  reference_type: string | null;
  reference_id: string | null;
  created_at: string;
};

export type CreditPackage = { code: string; name: string; credits: number; price_cop_cents: number };

export type AdminUser = {
  id: string;
  email: string;
  display_name: string;
  status: string;
  created_at: string;
};
