export interface SchemaField {
  field_name: string;
  type: 'string' | 'number' | 'boolean';
  required: boolean;
}

export interface ValidationError {
  field: string;
  message: string;
}

/**
 * Validates that attributes match the dynamic category schema.
 * Returns { valid: boolean, errors: ValidationError[], cleanedAttributes: any }
 */
export const validateAttributes = (
  schema: any,
  attributes: any
): { valid: boolean; errors: ValidationError[]; cleanedAttributes: any } => {
  const errors: ValidationError[] = [];
  const cleanedAttributes: any = {};

  // Check if schema is valid array
  const fields: SchemaField[] = Array.isArray(schema) ? schema : [];

  for (const field of fields) {
    const value = attributes[field.field_name];

    // Check required condition
    if (field.required && (value === undefined || value === null || value === '')) {
      errors.push({
        field: field.field_name,
        message: `Field '${field.field_name}' is required for this category.`,
      });
      continue;
    }

    // Check data type if value is present
    if (value !== undefined && value !== null && value !== '') {
      const actualType = typeof value;
      let typeMatches = false;

      if (field.type === 'string' && actualType === 'string') {
        typeMatches = true;
      } else if (field.type === 'number' && actualType === 'number' && !isNaN(value)) {
        typeMatches = true;
      } else if (field.type === 'boolean' && actualType === 'boolean') {
        typeMatches = true;
      }

      if (!typeMatches) {
        errors.push({
          field: field.field_name,
          message: `Field '${field.field_name}' must be of type '${field.type}'. Received type '${actualType}'.`,
        });
      } else {
        cleanedAttributes[field.field_name] = value;
      }
    }
  }

  return {
    valid: errors.length === 0,
    errors,
    cleanedAttributes,
  };
};
