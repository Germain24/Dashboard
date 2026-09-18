"use client";

/**
 * Hook léger de validation Zod pour formulaires simples.
 * Ajoute la validation inline sans dépendre de react-hook-form.
 *
 * Usage :
 *   const { errors, validate, fieldError } = useZodForm(mySchema);
 *   // Dans onSubmit :
 *   const data = validate(formValues);
 *   if (!data) return; // validation failed, errors affichées
 */

import { useState, useCallback } from "react";
import type { z } from "zod";

type FieldErrors = Record<string, string>;

export function useZodForm<S extends z.ZodType>(_schema: S) {
  const [errors, setErrors] = useState<FieldErrors>({});

  const validate = useCallback(
    <T,>(data: T): T | null => {
      const result = _schema.safeParse(data);
      if (!result.success) {
        const fieldErrors: FieldErrors = {};
        for (const issue of result.error.issues) {
          const key = issue.path.join(".");
          if (!fieldErrors[key]) fieldErrors[key] = issue.message;
        }
        setErrors(fieldErrors);
        return null;
      }
      setErrors({});
      return result.data;
    },
    [_schema],
  );

  const fieldError = useCallback(
    (name: string): string | undefined => errors[name],
    [errors],
  );

  const clearErrors = useCallback(() => setErrors({}), []);

  return { errors, validate, fieldError, clearErrors };
}
