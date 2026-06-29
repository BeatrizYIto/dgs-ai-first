import { z } from "zod";
import { logger } from "../shared/logger.js";

export const StructuredResponseSchema = z.object({
  answer: z
    .string()
    .min(1, "answer must not be empty")
    .describe("The assistant's response to the user question"),

  source_document: z
    .string()
    .min(1, "source_document must not be empty")
    .describe("Name or identifier of the document used as source"),

  confidence_score: z
    .number()
    .min(0, "confidence_score must be at least 0")
    .max(1, "confidence_score must be at most 1")
    .describe("Confidence level of the answer, from 0 (low) to 1 (high)"),
}).strict();

export type StructuredResponse = z.infer<typeof StructuredResponseSchema>;

const SAFE_DEFAULT: StructuredResponse = {
  answer:
    "Não foi possível processar sua solicitação. Por favor, tente novamente ou entre em contato com o suporte.",
  source_document: "fallback",
  confidence_score: 0,
};

// Guardrail 3: answer must be in Portuguese — all source documents are in PT-BR.
// Uses two signals: (1) characters exclusive to Portuguese (ã, õ) and (2) high-frequency
// Portuguese function words that do not appear in English.
function passesPortugueseLanguageGuardrail(answer: string): boolean {
  if (/[ãõÃÕ]/.test(answer)) return true;

  return /\b(não|está|são|também|então|assim|pelo|pela|isso|esse|essa|seria|foram|precisa)\b/i.test(
    answer,
  );
}

// Guardrail 2: when 'carga perigosa' and 'devolução' both appear, the answer must contain a negation.
// Without negation the response would be affirming that returning dangerous cargo is possible,
// which violates the business rule.
function passesDangerousCargoGuardrail(answer: string): boolean {
  const lower = answer.toLowerCase();

  const hasDangerousCargo =
    /cargas?\s+perigosas?|material\s+perigoso|produto\s+perigoso/.test(lower);
  const hasReturn =
    /devolu[cç][aã]o|devolver(do|ndo)?|retorno\s+de\s+carga/.test(lower);

  if (!hasDangerousCargo || !hasReturn) {
    return true;
  }

  const negationMarkers = [
    "não",
    "nao",
    "impossível",
    "impossivel",
    "proibido",
    "vedado",
    "negado",
    "não é possível",
    "não é permitido",
    "não é permitida",
    "não pode",
  ];

  return negationMarkers.some((marker) => lower.includes(marker));
}

export function validateResponse(raw: unknown): StructuredResponse {
  const parsed = StructuredResponseSchema.safeParse(raw);

  if (!parsed.success) {
    logger.warn(
      {
        operation: "validate-response",
        errors: parsed.error.errors,
      },
      "Response failed schema validation — returning safe default",
    );
    return { ...SAFE_DEFAULT };
  }

  const response = parsed.data;

  // Guardrail 1: source_document is required (Zod already enforces min(1), but we
  // explicitly reject here to make the guardrail intent clear and log a distinct reason).
  if (!response.source_document.trim()) {
    logger.warn(
      {
        operation: "validate-response",
        guardrail: "G1_source_document_required",
        reason: "source_document is absent or blank",
      },
      "Guardrail 1 violated — returning safe default",
    );
    return { ...SAFE_DEFAULT };
  }

  // Guardrail 2: responses about dangerous cargo and return must contain explicit negation.
  if (!passesDangerousCargoGuardrail(response.answer)) {
    logger.warn(
      {
        operation: "validate-response",
        guardrail: "G2_dangerous_cargo_return",
        reason:
          "Answer mentions 'carga perigosa' + 'devolução' without a negation — possible affirmation of illegal return blocked",
      },
      "Guardrail 2 violated — returning safe default",
    );
    return { ...SAFE_DEFAULT };
  }

  // Guardrail 3: answer must be in Portuguese — all source documents are PT-BR.
  if (!passesPortugueseLanguageGuardrail(response.answer)) {
    logger.warn(
      {
        operation: "validate-response",
        guardrail: "G3_portuguese_language_required",
        reason: "Answer does not appear to be in Portuguese — source documents are PT-BR only",
      },
      "Guardrail 3 violated — returning safe default",
    );
    return { ...SAFE_DEFAULT };
  }

  return response;
}
