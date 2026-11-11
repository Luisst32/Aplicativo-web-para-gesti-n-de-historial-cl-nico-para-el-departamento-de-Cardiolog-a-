# Cardiovascular Clinical System - Relational Database Architecture

This document defines the complete relational database architecture and entity-relationship model for the Clinical Evaluation and Cardiovascular Health Monitoring System (CardioUNEMI / ESPOL).

The architecture is designed to be fully compatible with PostgreSQL and modern cloud platforms such as **Supabase**, adopting UUID primary keys for entities managed by Supabase Auth and standard relational integrity constraints.

---

## 1. Naming Conventions

All database relations strictly adhere to the following naming convention:

- **`m_` (Master / Catalog Tables)**: Static, reference, dimension, or lookup entities that define the system taxonomy, geographical divisions, academic roles, and standardized clinical scales (e.g., `m_users`, `m_roles`, `m_institutions`, `m_cantons`).
- **`t_` (Transactional Tables)**: Dynamic entities that record clinical encounters, medical events, evaluations, laboratory findings, physical exams, study requests, and system mutations over time (e.g., `t_patients`, `t_visits`, `t_electrocardiograms`, `t_ordered_studies`, `t_system_settings`).

---

## 2. Complete Mermaid Entity-Relationship Diagram

```mermaid
erDiagram
    %% ========================================================
    %% RELATIONSHIPS
    %% ========================================================

    %% Geographical and Academic Reference Hierarchy
    m_countries ||--o{ m_provinces : "contains"
    m_provinces ||--o{ m_cantons : "contains"
    m_cantons ||--o{ m_institutions : "located_in"

    %% Security and Role-Based Access Control
    m_users ||--o{ t_user_roles : "holds"
    m_roles ||--o{ t_user_roles : "assigned_to"
    m_roles ||--|| t_system_settings : "configures"
    m_users ||--o{ t_system_settings : "modified_by"
    m_users ||--o{ t_audit_change_logs : "performed_by"
    m_users ||--o{ t_bot_queries : "initiates"

    %% Patient Demographic Relationships
    m_institutions ||--o{ t_patients : "affiliates"
    m_sexes ||--o{ t_patients : "categorizes"
    m_ethnicities ||--o{ t_patients : "identifies"
    m_cantons ||--o{ t_patients : "birth_place"
    m_countries ||--o{ t_patients : "birth_country"
    m_users ||--o{ t_patients : "registered_by"

    %% Clinical Encounter & Socioeconomic Background
    t_patients ||--|| t_visits : "undergoes"
    m_users ||--o{ t_visits : "evaluated_by"
    m_staff_categories ||--o{ t_visits : "staff_category"
    m_professional_categories ||--o{ t_visits : "profession"
    m_education_levels ||--o{ t_visits : "education"
    m_income_ranges ||--o{ t_visits : "income"
    m_marital_statuses ||--o{ t_visits : "marital_status"
    m_living_situations ||--o{ t_visits : "living_situation"
    m_housing_types ||--o{ t_visits : "housing_type"
    m_work_schedules ||--o{ t_visits : "work_schedule"
    m_cantons ||--o{ t_visits : "residence"

    %% Specialized Clinical Modules (1:1 with Encounter)
    t_visits ||--|| t_anthropometries : "measures"
    t_visits ||--|| t_vital_signs : "monitors"
    t_visits ||--|| t_electrocardiograms : "records"
    m_ecg_rhythms ||--o{ t_electrocardiograms : "rhythm_type"
    t_visits ||--|| t_echocardiograms : "assesses"
    t_visits ||--|| t_laboratories : "analyzes"
    t_visits ||--|| t_ordered_studies : "prescribes"

    %% Universal Questionnaire Survey Model
    m_questionnaire_sections ||--o{ m_questions : "groups"
    m_questions ||--o{ m_question_options : "provides"
    t_visits ||--o{ t_visit_answers : "captures"
    m_questions ||--o{ t_visit_answers : "answers_to"
    m_question_options ||--o{ t_visit_answers : "selects"

    %% ========================================================
    %% MASTER TABLES (m_)
    %% ========================================================

    m_users {
        uuid id PK "Supabase auth UUID or primary key"
        string username UK "Unique platform handle"
        string email UK "Registered corporate email"
        string password_hash "Encrypted authentication secret"
        string first_name "Given names"
        string last_name "Paternal and maternal surnames"
        string status "ACTIVE | SUSPENDED"
        boolean is_staff "Staff administrative rights"
        boolean is_active "Authentication validity flag"
        timestamp created_at "Account creation timestamp"
    }

    m_roles {
        int id PK "Catalog serial role identifier"
        string code UK "Role unique code: Administrador | Medico"
        string name "Display title of authorization role"
        string description "Functional scope of permissions"
        string status "ACTIVE | INACTIVE"
    }

    m_institutions {
        int id PK "Catalog primary key"
        string code UK "Institution mnemonic: UNEMI | ESPOL"
        string name "Official academic institution name"
        int canton_id FK "Main campus canton"
        string status "ACTIVE | INACTIVE"
    }

    m_countries {
        int id PK "ISO catalog primary key"
        string code UK "ISO 3166-1 alpha-3 code (e.g. ECU)"
        string name "Full national country designation"
    }

    m_provinces {
        int id PK "State or province primary key"
        string code UK "National INEC province code"
        string name "Official province territory name"
        int country_id FK "Parent country relation"
    }

    m_cantons {
        int id PK "Canton or municipality primary key"
        string code UK "National INEC municipality code"
        string name "Designated city or canton name"
        int province_id FK "Parent province relation"
    }

    m_sexes {
        int id PK "Catalog primary key"
        string code UK "H | M"
        string name "Hombre | Mujer"
    }

    m_ethnicities {
        int id PK "Catalog primary key"
        string code UK "Taxonomic identifier"
        string name "Mestizo | Afroecuatoriano | Blanco | Montubio"
    }

    m_staff_categories {
        int id PK "Staff estate identifier"
        string code UK "PDI | AD | PAS | SERVICIO | ESTUDIANTES"
        string name "Official descriptive category"
    }

    m_professional_categories {
        int id PK "Career classification identifier"
        string code UK "Career taxonomy key"
        string name "Docente Titular | Auxiliar | Servidor Publico"
    }

    m_education_levels {
        int id PK "Instruction level identifier"
        string code UK "Scale grade key"
        string name "Primaria | Secundaria | Superior | Postgrado"
    }

    m_income_ranges {
        int id PK "Income bracket identifier"
        string code UK "Monetary range code"
        string name "Bracket definition in USD"
    }

    m_marital_statuses {
        int id PK "Civil status identifier"
        string code UK "Marital category key"
        string name "Soltero | Casado | Divorciado | Viudo"
    }

    m_living_situations {
        int id PK "Cohabitation identifier"
        string code UK "Household environment key"
        string name "Solo | Pareja | Hijos | Familiares"
    }

    m_housing_types {
        int id PK "Dwelling status identifier"
        string code UK "Housing property key"
        string name "Propia | Arrendada | Familiar | Prestada"
    }

    m_work_schedules {
        int id PK "Labor schedule identifier"
        string code UK "Shift pattern key"
        string name "Jornada Completa | Parcial | Rotativo"
    }

    m_ecg_rhythms {
        int id PK "Standard rhythm identifier"
        string code UK "ECG nomenclature: RS | RL | ACXFA"
        string name "Clinical rhythm diagnosis name"
    }

    m_questionnaire_sections {
        int id PK "Section order identifier"
        string code UK "Modular questionnaire section code"
        string title "Clinical heading description"
        int display_order "Visual module sorting index"
    }

    m_questions {
        int id PK "Questionnaire item identifier"
        int section_id FK "Enclosing questionnaire module"
        string code UK "Standard epidemiological variable name"
        string text "Clinical question label verbatim"
        string response_type "RADIO | CHECKBOX | TEXT | NUMERIC"
        int display_order "Sequential item index"
    }

    m_question_options {
        int id PK "Catalog option item identifier"
        int question_id FK "Target question relation"
        string option_code "Internal variable value"
        string option_text "User display string"
        decimal numeric_value "SPSS coded numeric value"
        int display_order "Sequential presentation order"
    }

    %% ========================================================
    %% TRANSACTIONAL TABLES (t_)
    %% ========================================================

    t_user_roles {
        uuid id PK "Supabase record UUID"
        uuid user_id FK "Application user relation"
        int role_id FK "Granted security role"
        string status "ACTIVE | INACTIVE"
        timestamp assigned_at "Authorization granting timestamp"
        uuid assigned_by_id FK "Granting administrator relation"
    }

    t_system_settings {
        uuid id PK "Configuration record UUID"
        int authorized_role_id FK "Authorized management role (Administrador)"
        text gemini_api_key_encrypted "Fernet-encrypted Gemini generative API key"
        string gemini_model "Configured model: gemini-2.5-flash"
        boolean chatbot_enabled "Global clinical assistant enable flag"
        string gmail_client_id "Google Cloud OAuth2 Client Identifier"
        text gmail_client_secret_encrypted "Fernet-encrypted OAuth2 client secret"
        text gmail_refresh_token_encrypted "Fernet-encrypted offline refresh token"
        string gmail_sender_email "Automated outbound notification email address"
        boolean gmail_api_enabled "Gmail dispatch integration active flag"
        string gmail_redirect_uri "OAuth2 authorized redirect URI callback"
        timestamp last_token_refresh "Most recent OAuth2 token renewal date"
        uuid updated_by_id FK "Accountable administrator relation"
        timestamp updated_at "Last settings mutation timestamp"
    }

    t_patients {
        uuid patient_id PK "Unique Supabase / Postgres patient identity"
        int institution_id FK "Affiliated academic institution"
        string id_card UK "National identity card number (Cedula)"
        string first_names "Patient given names"
        string last_name1 "Primary family surname"
        string last_name2 "Secondary maternal surname"
        date birth_date "Date of birth"
        int sex_id FK "Demographic biological sex"
        int ethnicity_id FK "Declared ethnic background"
        int birth_canton_id FK "Domestic birth canton (if Ecuador)"
        int birth_country_id FK "Foreign birth country (if abroad)"
        string foreign_birth_place "Foreign municipality or state"
        string email "Electronic contact address"
        string phone "Contact telephone with international prefix"
        string status "ACTIVE | INACTIVE"
        timestamp created_at "Registration creation timestamp"
        uuid created_by_id FK "Clinician who recorded patient"
    }

    t_visits {
        uuid visit_id PK "Unique evaluation encounter identifier"
        uuid patient_id FK "Subject patient evaluated (1:1 relation)"
        uuid evaluator_id FK "Attending physician / clinician"
        int visit_number "Sequential consultation encounter number"
        string study_code UK "Unique protocol code: e.g. 0499-2026"
        date visit_date "Clinical encounter date"
        int study_year "Extracted annual cohort indicator"
        string status "PENDING | COMPLETED | CANCELLED"
        int staff_category_id FK "University staff classification"
        int professional_category_id FK "Academic appointment tier"
        int education_level_id FK "Highest attained instruction level"
        int income_range_id FK "Monthly household income bracket"
        int marital_status_id FK "Marital status during consultation"
        int living_situation_id FK "Household cohabitation structure"
        int housing_type_id FK "Dwelling ownership classification"
        int work_schedule_id FK "Workday labor distribution"
        int residence_canton_id FK "Current residence canton"
        string faculty "Academic university faculty"
        timestamp created_at "Visit record initiation timestamp"
    }

    t_anthropometries {
        uuid anthropometry_id PK "Biometric record UUID"
        uuid visit_id FK "Unique visit relationship (1:1)"
        decimal weight_kg "Body weight in kilograms"
        decimal height_m "Height in meters"
        decimal bmi "Computed Body Mass Index (kg/m2)"
        decimal body_surface_area "Calculated DuBois Body Surface Area (m2)"
        decimal abdominal_circumference_cm "Waist circumference in cm"
        decimal hip_circumference_cm "Hip perimeter in cm"
        decimal waist_hip_ratio "Abdominal to hip perimeter ratio"
        timestamp created_at "Measurement record timestamp"
    }

    t_vital_signs {
        uuid vital_signs_id PK "Hemodynamic assessment UUID"
        uuid visit_id FK "Unique visit relationship (1:1)"
        int systolic_bp "Systolic Blood Pressure (mmHg)"
        int diastolic_bp "Diastolic Blood Pressure (mmHg)"
        int heart_rate "Radial pulse / Heart Rate (bpm)"
        decimal oxygen_saturation "Peripheral capillary SpO2 (%)"
        decimal temperature_c "Core body temperature in Celsius"
        timestamp created_at "Vital signs logging timestamp"
    }

    t_electrocardiograms {
        uuid ecg_id PK "Cardiovascular tracing UUID"
        uuid visit_id FK "Unique visit relationship (1:1)"
        int rhythm_id FK "Standardized ECG rhythm classification"
        int heart_rate "Ventricular response rate (bpm)"
        int qrs_axis_degrees "Frontal plane QRS electric axis"
        decimal rr_interval_sec "Mean RR cycle duration in seconds"
        decimal p_wave_mm "P wave voltage amplitude in mm"
        int pr_interval_ms "Atrioventricular conduction PR interval (ms)"
        int qrs_duration_ms "Ventricular depolarization duration (ms)"
        int qt_interval_ms "Total electrical systole duration (ms)"
        int qtc_bazett_ms "Heart rate corrected QT interval (Bazett formula)"
        boolean p_mitrale "P wave broadening indicative of left atrial dilation"
        boolean av_block "Atrioventricular conduction impairment presence"
        string av_block_grade "AV Block severity: Degree I | II (Mobitz I/II) | III"
        boolean sa_block "Sinoatrial node exit block presence"
        boolean interatrial_block "Interatrial Bachmann bundle conduction block"
        boolean hemiblock "Presence of ventricular hemiblock / fascicular block"
        string hemiblock_detail "Fascicular hemiblock: Anterior | Posterior"
        boolean has_bundle_branch_block "Presence of main bundle branch delay"
        string bundle_branch_block "Bundle branch block type: RBBB | LBBB"
        boolean brugada_pattern "Brugada pseudo-RBBB and ST elevation pattern"
        boolean early_repolarization "Benign early repolarization J-point elevation"
        boolean left_ventricular_hypertrophy "Sokolow-Lyon or Cornell voltage criteria"
        boolean systolic_overload "Strain pattern indicative of ventricular overload"
        string systolic_overload_complexes "Leads manifesting systolic strain"
        decimal intrinsicoid_deflection_sec "Ventricular activation time in V5-V6 (sec)"
        boolean right_ventricular_hypertrophy "Right ventricular strain / voltage criteria"
        boolean delta_wave "Pre-excitation slurred QRS upstroke (WPW)"
        boolean digitalis_effect "Characteristic 'sagging' ST segment depression"
        boolean pathological_q_wave "Infarction necrosis Q-wave presence"
        string q_wave_amplitude "Q wave morphological depth/breadth description"
        decimal q_wave_voltage_mv "Pathological Q wave voltage in mV"
        string q_wave_complexes "Leads presenting pathological necrosis Q waves"
        boolean negative_t_wave "Ischemic or strain inverted T waves"
        string negative_t_complexes "Leads manifesting inverted T wave morphology"
        boolean negative_t_symmetric "Symmetric T wave inversion (ischemic)"
        boolean negative_t_asymmetric "Asymmetric T wave inversion (strain/secondary)"
        boolean st_elevation_pathological "Acute injury ST elevation (STEMI pattern)"
        decimal st_elevation_mm "ST segment elevation magnitude in mm"
        string st_elevation_complexes "Anatomical leads exhibiting ST elevation"
        boolean st_depression "Subendocardial ischemia ST depression"
        decimal st_depression_mm "ST segment depression magnitude in mm"
        string st_depression_complexes "Anatomical leads exhibiting ST depression"
        boolean is_normal "Overall normal tracing assessment flag"
        boolean repolarization_abnormalities "Non-specific repolarization disturbances"
        text ecg_comments "Specialist narrative diagnosis and remarks"
        timestamp created_at "ECG interpretation recording timestamp"
    }

    t_echocardiograms {
        uuid echo_id PK "Doppler echocardiogram study UUID"
        uuid visit_id FK "Unique visit relationship (1:1)"
        decimal lv_diastolic_diameter_mm "Left Ventricular End-Diastolic Dimension (LVEDD)"
        decimal lv_systolic_diameter_mm "Left Ventricular End-Systolic Dimension (LVESD)"
        decimal ivs_thickness_mm "Interventricular Septum thickness (IVSd)"
        decimal posterior_wall_thickness_mm "Left Ventricular Posterior Wall thickness (LVPWd)"
        decimal la_diameter_mm "Left Atrial anteroposterior diameter"
        decimal aortic_root_diameter_mm "Sinus of Valsalva / Aortic root dimension"
        decimal lvef_percentage "Left Ventricular Ejection Fraction (Teichholz / Simpson)"
        boolean ventricular_hypertrophy "Ventricular wall hypertrophy assessment"
        boolean diastolic_dysfunction "Impaired ventricular relaxation / filling"
        boolean aortic_valve_calcification "Sclerotic degeneration of aortic leaflets"
        string valvular_regurgitation_detail "Valvulopathy location and grade"
        text echo_comments "Echocardiography narrative evaluation"
        timestamp created_at "Echo registration timestamp"
    }

    t_laboratories {
        uuid lab_id PK "Laboratory blood work panel UUID"
        uuid visit_id FK "Unique visit relationship (1:1)"
        decimal glucose_mg_dl "Fasting blood glucose (mg/dL)"
        decimal urea_mg_dl "Blood urea nitrogen / urea concentration (mg/dL)"
        decimal creatinine_mg_dl "Serum creatinine concentration (mg/dL)"
        decimal total_cholesterol_mg_dl "Total serum cholesterol (mg/dL)"
        decimal hdl_mg_dl "High-density lipoprotein cholesterol (mg/dL)"
        decimal ldl_mg_dl "Low-density lipoprotein cholesterol (mg/dL)"
        decimal triglycerides_mg_dl "Serum triglycerides concentration (mg/dL)"
        decimal ast_got_u_l "Aspartate aminotransferase (AST / GOT) (U/L)"
        decimal alt_gpt_u_l "Alanine aminotransferase (ALT / GPT) (U/L)"
        decimal ggt_u_l "Gamma-glutamyl transferase (GGT) (U/L)"
        decimal tsh_u_iu_ml "Thyroid-stimulating hormone (uIU/mL)"
        decimal hemoglobin_g_dl "Blood hemoglobin concentration (g/dL)"
        decimal hematocrit_percentage "Hematocrit packed cell volume (%)"
        decimal rbc_millions "Red blood cell count (millions/uL)"
        decimal wbc_thousands "White blood cell count (thousands/uL)"
        decimal platelets_thousands "Thrombocyte count (thousands/uL)"
        decimal mcv_fl "Mean corpuscular volume (fL)"
        decimal prothrombin_time_sec "Prothrombin time / INR seconds"
        timestamp created_at "Laboratory processing timestamp"
    }

    t_ordered_studies {
        uuid study_id PK "Study prescription record UUID"
        uuid visit_id FK "Unique visit relationship (1:1)"
        boolean clinical_analysis "Item 1: Comprehensive blood and urine workup requested"
        boolean ergometry_spect "Item 2: SPECT myocardial perfusion treadmill stress test"
        boolean cardiac_ct "Item 3: Multislice Coronary Computed Tomography Angiography"
        boolean cardiac_mri "Item 4: Cardiac Magnetic Resonance Imaging study"
        boolean electrophysiology "Item 5: Invasive / diagnostic electrophysiology study"
        boolean echocardiogram_ordered "Item 6: Transthoracic Doppler Echocardiography indicated"
        boolean holter_ordered "Item 7: Ambulatory 24-hour Holter ECG monitor"
        boolean mapa_ordered "Item 8: Ambulatory Blood Pressure Monitoring (MAPA) 24h"
        text other_studies "Narrative clinical indications and complementary exams"
        timestamp created_at "Prescription logging timestamp"
    }

    t_visit_answers {
        bigint answer_id PK "Survey answer serial identifier"
        uuid visit_id FK "Parent clinical evaluation visit"
        int question_id FK "Answered questionnaire item"
        int selected_option_id FK "Selected catalog choice (for categorical items)"
        text text_value "Open narrative or alphanumeric response"
        decimal numeric_value "Numeric metric response"
        timestamp created_at "Answer submission timestamp"
    }

    t_audit_change_logs {
        bigint change_log_id PK "Audit event sequence identifier"
        timestamp timestamp "UTC moment when mutation occurred"
        string schema_name "Target PostgreSQL schema (clinical | security | catalog)"
        string table_name "Mutated relation name"
        string record_key "Primary key identifier of altered row"
        string action "Operation: INSERT | UPDATE | DELETE"
        string column_name "Modified attribute name"
        text old_value "Serialized state prior to modification"
        text new_value "Serialized state following modification"
        string status "RECORDED | VERIFIED | FLAGGED"
        uuid user_id FK "Authenticated operator responsible"
        string db_login "PostgreSQL database session role"
        string machine_name "Client IP address or machine hostname"
    }

    t_bot_queries {
        bigint bot_query_id PK "Assistant interaction sequence identifier"
        uuid user_id FK "Authenticated specialist submitting query"
        text user_question "Natural language clinical inquiry"
        text generated_sql "Synthesized read-only analytics SQL query"
        text bot_response "Synthesized AI response and clinical guidance"
        int tokens_used "Total LLM tokens consumed in completion"
        int execution_time_ms "Processing latency in milliseconds"
        string status "SUCCESS | ERROR | PENDING"
        timestamp created_at "Timestamp of assistant transaction"
    }
```

---

## 3. Data Dictionary: Tables & Parameters

### 3.1. Security & Configuration (`m_` & `t_`)

#### `m_users`
Stores user credentials, staff privileges, and core account status.
- `id` (`uuid`, **PK**): Primary key identifier (compatible with `auth.users` in Supabase).
- `username` (`varchar(150)`, **UK**): Unique system username.
- `email` (`varchar(254)`, **UK**): Electronic mail address used for communication and password resets.
- `password_hash` (`varchar(128)`): Salted cryptographic hash of the user password.
- `first_name` (`varchar(150)`): Given name(s).
- `last_name` (`varchar(150)`): Family surname(s).
- `status` (`varchar(20)`): Account lifecycle status (`ACTIVE`, `SUSPENDED`).
- `is_staff` (`boolean`): Access flag to backoffice administrative modules.
- `is_active` (`boolean`): Active indicator for user authentication sessions.
- `created_at` (`timestamptz`): Timestamp of user provisioning.

#### `m_roles`
Defines operational profiles and RBAC security boundaries.
- `id` (`integer`, **PK**): Unique integer identifier.
- `code` (`varchar(50)`, **UK**): Immutable mnemonic (`Administrador`, `Medico`, `Investigador`).
- `name` (`varchar(100)`): User-facing display title.
- `description` (`text`): Detailed administrative scope and authority.
- `status` (`varchar(20)`): Role operational status (`ACTIVE`, `INACTIVE`).

#### `t_user_roles`
Transactional assignment linking users to security roles.
- `id` (`uuid`, **PK**): Unique assignment identifier.
- `user_id` (`uuid`, **FK**): References `m_users.id`.
- `role_id` (`integer`, **FK**): References `m_roles.id`.
- `status` (`varchar(20)`): State of permission assignment (`ACTIVE`, `INACTIVE`).
- `assigned_at` (`timestamptz`): Moment when privilege was granted.
- `assigned_by_id` (`uuid`, **FK**): References `m_users.id` who authorized the role.

#### `t_system_settings` (APIs & System Credentials)
Single-source transactional configuration storing external API credentials, dedicated encryption keys, and integrations.
- `id` (`uuid`, **PK**): Unique setting row identifier.
- `authorized_role_id` (`integer`, **FK**, **UK**): References `m_roles.id` (strictly restricted to `Administrador`).
- `gemini_api_key_encrypted` (`text`): Fernet-encrypted Google Gemini API secret.
- `gemini_model` (`varchar(100)`): Gemini model version (default: `gemini-2.5-flash`).
- `chatbot_enabled` (`boolean`): Master toggle for the clinical AI assistant.
- `gmail_client_id` (`varchar(255)`): Google Cloud OAuth2 Client ID for automated transactional emailing.
- `gmail_client_secret_encrypted` (`text`): Fernet-encrypted OAuth2 client secret.
- `gmail_refresh_token_encrypted` (`text`): Fernet-encrypted OAuth2 offline refresh token.
- `gmail_sender_email` (`varchar(254)`): Verified sender email address (e.g., `notificaciones@unemi.edu.ec`).
- `gmail_api_enabled` (`boolean`): Toggle for active email notifications via Gmail REST API.
- `gmail_redirect_uri` (`varchar(255)`): Authorized OAuth2 callback endpoint.
- `last_token_refresh` (`timestamptz`): Timestamp of the last successful token generation or validation.
- `updated_by_id` (`uuid`, **FK**): References `m_users.id` who saved the credentials.
- `updated_at` (`timestamptz`): Last update timestamp.

---

### 3.2. Patient & Encounter Registry (`t_` & `m_`)

#### `t_patients`
Central master identity for every individual evaluated across university cohorts.
- `patient_id` (`uuid`, **PK**): Unique patient surrogate identity.
- `institution_id` (`integer`, **FK**): References `m_institutions.id` (e.g., UNEMI vs. ESPOL).
- `id_card` (`varchar(13)`, **UK**): National citizenship identification card (Cédula).
- `first_names` (`varchar(100)`): Patient given names.
- `last_name1` (`varchar(50)`): Paternal family name.
- `last_name2` (`varchar(50)`): Maternal family name.
- `birth_date` (`date`): Date of birth.
- `sex_id` (`integer`, **FK**): References `m_sexes.id`.
- `ethnicity_id` (`integer`, **FK**): References `m_ethnicities.id`.
- `birth_canton_id` (`integer`, **FK**, nullable): Domestic canton of birth if born in Ecuador (`m_cantons.id`).
- `birth_country_id` (`integer`, **FK**, nullable): Birth country if born abroad (`m_countries.id`).
- `foreign_birth_place` (`varchar(80)`, nullable): Foreign locality if born abroad.
- `email` (`varchar(100)`): Contact electronic email.
- `phone` (`varchar(20)`): Contact telephone with international prefix.
- `status` (`varchar(20)`): Clinical file state (`ACTIVE`, `INACTIVE`).
- `created_at` (`timestamptz`): Clinical registration creation timestamp.
- `created_by_id` (`uuid`, **FK**): Attending healthcare provider who opened the file.

#### `t_visits`
Clinical encounter record representing a comprehensive cardiovascular consultation.
- `visit_id` (`uuid`, **PK**): Primary key identifier of the clinical encounter.
- `patient_id` (`uuid`, **FK**, **UK**): 1:1 relation to `t_patients.patient_id`.
- `evaluator_id` (`uuid`, **FK**): Evaluating medical specialist (`m_users.id`).
- `visit_number` (`smallint`): Ordinal visit number (default: `1`).
- `study_code` (`varchar(30)`, **UK**): Unique research study tracking code (e.g., `0499/2026`).
- `visit_date` (`date`): Date of the physical examination and questionnaire completion.
- `study_year` (`integer`): Computed / extracted annual cohort year.
- `status` (`varchar(20)`): Encounter status (`PENDING`, `COMPLETED`, `CANCELLED`).
- `staff_category_id` (`integer`, **FK**): Category (`m_staff_categories.id`).
- `professional_category_id` (`integer`, **FK**): Career tier (`m_professional_categories.id`).
- `education_level_id` (`integer`, **FK**): Education grade (`m_education_levels.id`).
- `income_range_id` (`integer`, **FK**): Monthly income bracket (`m_income_ranges.id`).
- `marital_status_id` (`integer`, **FK**): Civil marital status (`m_marital_statuses.id`).
- `living_situation_id` (`integer`, **FK**): Domestic cohabitation (`m_living_situations.id`).
- `housing_type_id` (`integer`, **FK**): Dwelling property status (`m_housing_types.id`).
- `work_schedule_id` (`integer`, **FK**): Work shift pattern (`m_work_schedules.id`).
- `residence_canton_id` (`integer`, **FK**): City/Canton of residence (`m_cantons.id`).
- `faculty` (`varchar(100)`): Academic faculty of affiliation.
- `created_at` (`timestamptz`): Visit initiation date and time.

---

### 3.3. Specialized Cardiovascular Evaluation Tables (`t_`)

#### `t_anthropometries`
- `anthropometry_id` (`uuid`, **PK**)
- `visit_id` (`uuid`, **FK**, **UK**): References `t_visits.visit_id`.
- `weight_kg` (`decimal(5,2)`): Weight in kg.
- `height_m` (`decimal(4,2)`): Height in meters.
- `bmi` (`decimal(5,2)`): Calculated Body Mass Index.
- `body_surface_area` (`decimal(4,2)`): Calculated BSA ($m^2$).
- `abdominal_circumference_cm` (`decimal(5,2)`): Waist circumference in cm.
- `hip_circumference_cm` (`decimal(5,2)`): Hip circumference in cm.
- `waist_hip_ratio` (`decimal(4,2)`): WHR index.
- `created_at` (`timestamptz`): Log timestamp.

#### `t_vital_signs`
- `vital_signs_id` (`uuid`, **PK**)
- `visit_id` (`uuid`, **FK**, **UK**): References `t_visits.visit_id`.
- `systolic_bp` (`smallint`): Systolic Blood Pressure (mmHg).
- `diastolic_bp` (`smallint`): Diastolic Blood Pressure (mmHg).
- `heart_rate` (`smallint`): Heart rate (bpm).
- `oxygen_saturation` (`decimal(4,1)`): SpO2 percentage.
- `temperature_c` (`decimal(3,1)`): Body temperature (°C).
- `created_at` (`timestamptz`): Log timestamp.

#### `t_electrocardiograms` (27 Comprehensive Tracing Items)
- `ecg_id` (`uuid`, **PK**)
- `visit_id` (`uuid`, **FK**, **UK**): References `t_visits.visit_id`.
- `rhythm_id` (`integer`, **FK**): References `m_ecg_rhythms.id`.
- `heart_rate` (`smallint`): Heart rate (bpm).
- `qrs_axis_degrees` (`smallint`): Frontal plane QRS axis (°).
- `rr_interval_sec` (`decimal(4,2)`): RR interval in seconds.
- `p_wave_mm` (`decimal(4,2)`): P wave voltage in mm.
- `pr_interval_ms` (`smallint`): PR interval duration in ms.
- `qrs_duration_ms` (`smallint`): QRS duration in ms.
- `qt_interval_ms` (`smallint`): Raw QT interval in ms.
- `qtc_bazett_ms` (`smallint`): Corrected QTc in ms (Bazett formula).
- `p_mitrale` (`boolean`): Presence of P mitrale.
- `av_block` (`boolean`): Atrioventricular block flag.
- `av_block_grade` (`varchar(50)`): AV block grade description.
- `sa_block` (`boolean`): Sinoatrial block flag.
- `interatrial_block` (`boolean`): Interatrial block flag.
- `hemiblock` (`boolean`): Hemiblock presence.
- `hemiblock_detail` (`varchar(100)`): Fascicular detail.
- `has_bundle_branch_block` (`boolean`): Bundle branch block flag.
- `bundle_branch_block` (`varchar(100)`): RBBB / LBBB descriptor.
- `brugada_pattern` (`boolean`): Brugada pattern sign.
- `early_repolarization` (`boolean`): Early repolarization pattern.
- `left_ventricular_hypertrophy` (`boolean`): Voltage criteria for LVH.
- `systolic_overload` (`boolean`): Systolic strain pattern.
- `systolic_overload_complexes` (`varchar(100)`): Affected leads.
- `intrinsicoid_deflection_sec` (`decimal(5,3)`): V5-V6 intrinsicoid time.
- `right_ventricular_hypertrophy` (`boolean`): RVH criteria.
- `delta_wave` (`boolean`): Delta wave / WPW pattern.
- `digitalis_effect` (`boolean`): Digitalis scoop effect.
- `pathological_q_wave` (`boolean`): Necrosis Q wave flag.
- `q_wave_amplitude` (`varchar(50)`): Q wave amplitude description.
- `q_wave_voltage_mv` (`decimal(4,2)`): Q wave voltage (mV).
- `q_wave_complexes` (`varchar(100)`): Leads with Q waves.
- `negative_t_wave` (`boolean`): Inverted T wave presence.
- `negative_t_complexes` (`varchar(100)`): Leads with inverted T waves.
- `negative_t_symmetric` (`boolean`): Symmetric inversion flag.
- `negative_t_asymmetric` (`boolean`): Asymmetric inversion flag.
- `st_elevation_pathological` (`boolean`): ST elevation presence.
- `st_elevation_mm` (`decimal(4,1)`): ST elevation magnitude (mm).
- `st_elevation_complexes` (`varchar(100)`): Leads with ST elevation.
- `st_depression` (`boolean`): ST depression presence.
- `st_depression_mm` (`decimal(4,1)`): ST depression magnitude (mm).
- `st_depression_complexes` (`varchar(100)`): Leads with ST depression.
- `is_normal` (`boolean`): Global normal ECG evaluation.
- `repolarization_abnormalities` (`boolean`): Non-specific repolarization disturbances.
- `ecg_comments` (`text`): Narrative electrophysiological observations.
- `created_at` (`timestamptz`): Log timestamp.

#### `t_ordered_studies` (Clinical Studies Prescribed)
- `study_id` (`uuid`, **PK**): Primary key identifier.
- `visit_id` (`uuid`, **FK**, **UK**): 1:1 relation to `t_visits.visit_id`.
- `clinical_analysis` (`boolean`): Item 1: Clinical laboratory tests ordered.
- `ergometry_spect` (`boolean`): Item 2: SPECT myocardial stress ergometry.
- `cardiac_ct` (`boolean`): Item 3: Cardiac CT scan.
- `cardiac_mri` (`boolean`): Item 4: Cardiac Magnetic Resonance.
- `electrophysiology` (`boolean`): Item 5: Electrophysiology study.
- `echocardiogram_ordered` (`boolean`): Transthoracic echocardiogram.
- `holter_ordered` (`boolean`): Ambulatory 24h Holter ECG.
- `mapa_ordered` (`boolean`): Ambulatory Blood Pressure Monitor (MAPA).
- `other_studies` (`text`): Observations and additional medical indications.
- `created_at` (`timestamptz`): Log timestamp.

#### `t_laboratories`
- `lab_id` (`uuid`, **PK**)
- `visit_id` (`uuid`, **FK**, **UK**): References `t_visits.visit_id`.
- `glucose_mg_dl` (`decimal(6,2)`)
- `urea_mg_dl` (`decimal(6,2)`)
- `creatinine_mg_dl` (`decimal(5,2)`)
- `total_cholesterol_mg_dl` (`decimal(6,2)`)
- `hdl_mg_dl` (`decimal(5,2)`)
- `ldl_mg_dl` (`decimal(6,2)`)
- `triglycerides_mg_dl` (`decimal(6,2)`)
- `ast_got_u_l` (`decimal(6,2)`)
- `alt_gpt_u_l` (`decimal(6,2)`)
- `ggt_u_l` (`decimal(6,2)`)
- `tsh_u_iu_ml` (`decimal(6,3)`)
- `hemoglobin_g_dl` (`decimal(4,2)`)
- `hematocrit_percentage` (`decimal(4,2)`)
- `rbc_millions` (`decimal(4,2)`)
- `wbc_thousands` (`decimal(5,2)`)
- `platelets_thousands` (`decimal(6,2)`)
- `mcv_fl` (`decimal(5,2)`)
- `prothrombin_time_sec` (`decimal(5,2)`)
- `created_at` (`timestamptz`): Log timestamp.

---

### 3.4. Audit, Interaction & Questionnaire Surveys (`t_`)

#### `t_visit_answers`
EAV survey storage capturing answers to all modular items of the questionnaire.
- `answer_id` (`bigint`, **PK**): Auto-incrementing answer sequence.
- `visit_id` (`uuid`, **FK**): References `t_visits.visit_id`.
- `question_id` (`integer`, **FK**): References `m_questions.id`.
- `selected_option_id` (`integer`, **FK**, nullable): Selected choice for discrete options (`m_question_options.id`).
- `text_value` (`text`, nullable): Alphanumeric response string.
- `numeric_value` (`decimal(10,3)`, nullable): Numeric observation value.
- `created_at` (`timestamptz`): Timestamp of submission.

#### `t_audit_change_logs`
System-wide audit trail recording row-level data modifications across all tables.
- `change_log_id` (`bigint`, **PK**): Primary key identifier.
- `timestamp` (`timestamptz`): UTC moment of mutation.
- `schema_name` (`varchar(50)`): Target PostgreSQL schema (`clinical`, `security`, `catalog`).
- `table_name` (`varchar(100)`): Mutated table name.
- `record_key` (`varchar(100)`): Primary key of the affected row.
- `action` (`varchar(10)`): Transaction type (`INSERT`, `UPDATE`, `DELETE`).
- `column_name` (`varchar(100)`, nullable): Mutated column name.
- `old_value` (`text`, nullable): Pre-mutation state.
- `new_value` (`text`, nullable): Post-mutation state.
- `status` (`varchar(20)`): Verification status (`RECORDED`, `VERIFIED`, `FLAGGED`).
- `user_id` (`uuid`, **FK**, nullable): Mutating user account (`m_users.id`).
- `db_login` (`varchar(100)`): PostgreSQL connection username.
- `machine_name` (`varchar(100)`): Client IP or hostname.

#### `t_bot_queries`
Audit and token consumption history for the clinical AI assistant.
- `bot_query_id` (`bigint`, **PK**): Sequence transaction identifier.
- `user_id` (`uuid`, **FK**): Inquiring clinician (`m_users.id`).
- `user_question` (`text`): Natural language clinical question.
- `generated_sql` (`text`, nullable): Generated read-only analytical query.
- `bot_response` (`text`): Assistant clinical answer and recommendations.
- `tokens_used` (`integer`, nullable): Total LLM token usage.
- `execution_time_ms` (`integer`, nullable): Response latency in milliseconds.
- `status` (`varchar(20)`): Execution outcome (`SUCCESS`, `ERROR`, `PENDING`).
- `created_at` (`timestamptz`): Interaction timestamp.

---

## 4. Key Architectural Takeaways

1. **Independent Surrogate Identity**: Every patient is uniquely identified by `t_patients.patient_id` and each consultation by `t_visits.visit_id`. This guarantees that cohorts from multiple institutions (e.g., UNEMI and ESPOL) can coexist without primary key collisions, even if both protocols use patient code `1`.
2. **Dedicated API Credential Encryption**: The `t_system_settings` table isolates external API secrets (`gemini_api_key_encrypted`, `gmail_client_secret_encrypted`, `gmail_refresh_token_encrypted`) encrypted with dedicated environment-driven keys using Multi-Fernet, strictly guarded by Role-Based Access Control (`m_roles.code = 'Administrador'`).
3. **Audit Compliance**: All clinical edits are transparently tracked in `t_audit_change_logs`, providing forensic traceability for biomedical ethics and institutional review boards.
