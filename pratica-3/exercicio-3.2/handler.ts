import { app, HttpRequest, HttpResponseInit } from "@azure/functions";
import { CosmosClient } from "@azure/cosmos";
import { z } from "zod";
import { logger } from "../../shared/logger";

const FeedbackSchema = z.object({
  queryId: z.string().uuid(),
  rating: z.number().int().min(1).max(5),
  comment: z.string().max(1000).optional(),
  attendantEmail: z.string().email(),
});

export async function feedbackHandler(
  request: HttpRequest,
): Promise<HttpResponseInit> {
  const parsed = FeedbackSchema.safeParse(await request.json());
  if (!parsed.success) {
    return { status: 400, body: JSON.stringify(parsed.error.flatten()) };
  }

  const feedback = { ...parsed.data, timestamp: new Date().toISOString() };

  logger.info(
    { queryId: feedback.queryId, rating: feedback.rating },
    "Feedback recebido",
  );

  const client = new CosmosClient(process.env.COSMOS_CONNECTION_STRING);
  const database = client.database("novatech");
  const container = database.container("feedbacks");

  await container.items.create(feedback);

  return { status: 200, body: "OK" };
}

app.http("feedback", {
  methods: ["POST"],
  handler: feedbackHandler,
});
