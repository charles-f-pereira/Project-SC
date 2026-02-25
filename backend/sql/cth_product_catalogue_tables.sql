-- Project SC: Product catalogue tables (CTH schema)
-- Database: GYG-CT-Helper, Schema: CTH
-- Source: Crunchtime getAllCompanyProductsEnhanced (companyProductEnhancedHeaderDetails, Concept, Department, UserDefinedCategory details)
--         and getAllCategories (categoryDetailDetails).
-- Run after cth_auto_allocation_tables.sql (schema CTH already exists).

-- Main product table: one row per company product from companyProductEnhancedHeaderDetails.
-- Columns map from API response; full payload also stored in raw_json.
CREATE TABLE IF NOT EXISTS "CTH"."CompanyProduct" (
    id                          BIGSERIAL PRIMARY KEY,
    number                      VARCHAR(50) NOT NULL,
    name                        VARCHAR(500) NULL,
    display_name                VARCHAR(500) NULL,
    description                 TEXT NULL,
    active_flag                 VARCHAR(1) NULL,
    product_id                  VARCHAR(100) NULL,
    category_name               VARCHAR(255) NULL,
    category_code               VARCHAR(100) NULL,
    subcategory_name            VARCHAR(255) NULL,
    subcategory_code            VARCHAR(100) NULL,
    microcategory_name          VARCHAR(255) NULL,
    microcategory_code          VARCHAR(100) NULL,
    bid_sheet                   VARCHAR(255) NULL,
    comment                     TEXT NULL,
    internal_comment            TEXT NULL,
    product_type                VARCHAR(50) NULL,
    product_group              VARCHAR(255) NULL,
    product_line                VARCHAR(255) NULL,
    primary_shipping_type       VARCHAR(100) NULL,
    secondary_shipping_type     VARCHAR(100) NULL,
    inventory_unit_package_type VARCHAR(50) NULL,
    preferred_vendor_unit_package_type VARCHAR(50) NULL,
    unit_of_measure            VARCHAR(50) NULL,
    default_unit_of_measure     VARCHAR(50) NULL,
    pack_size                   VARCHAR(100) NULL,
    case_size                   VARCHAR(100) NULL,
    order_multiple              VARCHAR(100) NULL,
    universal_product_code      VARCHAR(100) NULL,
    gl_number                   BIGINT NULL,
    gl_description              VARCHAR(500) NULL,
    cost_center                 VARCHAR(100) NULL,
    inventory_type              VARCHAR(100) NULL,
    brand                       VARCHAR(255) NULL,
    supplier_code               VARCHAR(100) NULL,
    taxable_flag                VARCHAR(1) NULL,
    orderable_flag              VARCHAR(1) NULL,
    sort_order                  INTEGER NULL,
    image_url                   VARCHAR(500) NULL,
    status                      VARCHAR(50) NULL,
    created_date                TIMESTAMPTZ NULL,
    last_modified_date          TIMESTAMPTZ NULL,
    raw_json                    JSONB NULL,
    updated_at                  TIMESTAMPTZ NULL,
    CONSTRAINT uq_companyproduct_number UNIQUE (number)
);

COMMENT ON TABLE "CTH"."CompanyProduct" IS 'Company products from Crunchtime getAllCompanyProductsEnhanced (companyProductEnhancedHeaderDetails). Used for product search/filter.';
COMMENT ON COLUMN "CTH"."CompanyProduct".number IS 'Product number (business key from API).';
COMMENT ON COLUMN "CTH"."CompanyProduct".raw_json IS 'Full header object from API for future fields.';
COMMENT ON COLUMN "CTH"."CompanyProduct".updated_at IS 'When this row was last upserted by the product catalogue sync (UTC).';

CREATE INDEX IF NOT EXISTS idx_companyproduct_number ON "CTH"."CompanyProduct"(number);
CREATE INDEX IF NOT EXISTS idx_companyproduct_name ON "CTH"."CompanyProduct"(name);
CREATE INDEX IF NOT EXISTS idx_companyproduct_category ON "CTH"."CompanyProduct"(category_name, subcategory_name, microcategory_name);

-- Lookup: concepts from companyProductEnhancedConceptDetails (code, activeFlag)
CREATE TABLE IF NOT EXISTS "CTH"."Concept" (
    code        VARCHAR(100) PRIMARY KEY,
    active_flag VARCHAR(1) NULL
);

COMMENT ON TABLE "CTH"."Concept" IS 'Concepts from Crunchtime company product enhanced (companyProductEnhancedConceptDetails). Filter products by concept.';

-- Lookup: departments from companyProductEnhancedDepartmentDetails
CREATE TABLE IF NOT EXISTS "CTH"."Department" (
    code        VARCHAR(100) PRIMARY KEY,
    active_flag VARCHAR(1) NULL
);

COMMENT ON TABLE "CTH"."Department" IS 'Departments from Crunchtime company product enhanced (companyProductEnhancedDepartmentDetails). Filter products by department.';

-- Lookup: user-defined categories from companyProductEnhancedUserDefinedCategoryDetails
CREATE TABLE IF NOT EXISTS "CTH"."UserDefinedCategories" (
    code        VARCHAR(255) PRIMARY KEY,
    active_flag VARCHAR(1) NULL
);

COMMENT ON TABLE "CTH"."UserDefinedCategories" IS 'User-defined categories from Crunchtime company product enhanced (companyProductEnhancedUserDefinedCategoryDetails). Filter products by UDC.';

-- Categories from getAllCategories (category/v1/getAllCategories) – one row per categoryDetailDetails element
CREATE TABLE IF NOT EXISTS "CTH"."Categories" (
    id                  BIGSERIAL PRIMARY KEY,
    category_name       VARCHAR(255) NULL,
    subcategory_name    VARCHAR(255) NULL,
    microcategory_name  VARCHAR(255) NULL,
    gl_description      VARCHAR(500) NULL,
    gl_number           BIGINT NULL,
    CONSTRAINT uq_categories_detail UNIQUE (category_name, subcategory_name, microcategory_name)
);

COMMENT ON TABLE "CTH"."Categories" IS 'Category catalogue from Crunchtime getAllCategories (categoryDetailDetails). Used for product filter.';

CREATE INDEX IF NOT EXISTS idx_categories_names ON "CTH"."Categories"(category_name, subcategory_name, microcategory_name);

-- Junction: product – concept (many-to-many)
CREATE TABLE IF NOT EXISTS "CTH"."CompanyProductConcept" (
    company_product_id BIGINT NOT NULL REFERENCES "CTH"."CompanyProduct"(id) ON DELETE CASCADE,
    concept_code       VARCHAR(100) NOT NULL REFERENCES "CTH"."Concept"(code) ON DELETE CASCADE,
    PRIMARY KEY (company_product_id, concept_code)
);

COMMENT ON TABLE "CTH"."CompanyProductConcept" IS 'Links company products to concepts (many-to-many). From companyProductEnhancedConceptDetails.';

CREATE INDEX IF NOT EXISTS idx_companyproductconcept_concept ON "CTH"."CompanyProductConcept"(concept_code);

-- Junction: product – department (many-to-many)
CREATE TABLE IF NOT EXISTS "CTH"."CompanyProductDepartment" (
    company_product_id BIGINT NOT NULL REFERENCES "CTH"."CompanyProduct"(id) ON DELETE CASCADE,
    department_code    VARCHAR(100) NOT NULL REFERENCES "CTH"."Department"(code) ON DELETE CASCADE,
    PRIMARY KEY (company_product_id, department_code)
);

COMMENT ON TABLE "CTH"."CompanyProductDepartment" IS 'Links company products to departments (many-to-many). From companyProductEnhancedDepartmentDetails.';

CREATE INDEX IF NOT EXISTS idx_companyproductdepartment_dept ON "CTH"."CompanyProductDepartment"(department_code);

-- Junction: product – user-defined category (many-to-many)
CREATE TABLE IF NOT EXISTS "CTH"."CompanyProductUserDefinedCategory" (
    company_product_id BIGINT NOT NULL REFERENCES "CTH"."CompanyProduct"(id) ON DELETE CASCADE,
    udc_code          VARCHAR(255) NOT NULL REFERENCES "CTH"."UserDefinedCategories"(code) ON DELETE CASCADE,
    PRIMARY KEY (company_product_id, udc_code)
);

COMMENT ON TABLE "CTH"."CompanyProductUserDefinedCategory" IS 'Links company products to user-defined categories (many-to-many). From companyProductEnhancedUserDefinedCategoryDetails.';

CREATE INDEX IF NOT EXISTS idx_companyproductudc_udc ON "CTH"."CompanyProductUserDefinedCategory"(udc_code);
