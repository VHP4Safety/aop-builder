import {Session} from "../models/Session.ts";
import {SessionWithResultResponse} from "../models/Result.ts";

export interface SessionService
{
    create(
        user_id: number,
        collection_id: number,
        title: string,
        key_events: string[],
        model_name: string,
        relevance_score_threshold: number
    ): Promise<Session>;
    getSessions(): Promise<Session[]>;
    getSession(id: number): Promise<Session>;
    getSessionWithChunks(id: number): Promise<Session>;
    submitSelectedChunks(sessionId: number, selectedDocuments: any[]): Promise<void>;
    resubmit(id: number, force?: boolean): Promise<{ message: string; session_id: number; status: string }>;
    remove(id: number): Promise<{ message: string; session_id: number }>;
    getSessionWithResult(id: number): Promise<SessionWithResultResponse>;
    getBudget(): Promise<{ budget: number }>;
}
