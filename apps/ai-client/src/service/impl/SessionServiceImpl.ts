import axios from 'axios';
import { SessionService } from "../SessionService.ts";
import { Session } from "../../models/Session.ts";
import {SessionWithResultResponse} from "../../models/Result.ts";

export class SessionServiceImpl implements SessionService {
    async create(
        user_id: number,
        collection_id: number,
        title: string,
        key_events: string[],
        model_name: string,
        relevance_score_threshold: number
    ): Promise<Session> {
        try {
            const response = await axios.post("/sessions/", {
                user_id,
                collection_id,
                title,
                key_events,
                model_name,
                relevance_score_threshold,
            });

            return response.data;
        } catch (error: any) {
            throw new Error(error.response?.data?.detail || 'An error occurred while creating the session.');
        }
    }

    async getSessions(): Promise<Session[]> {
        const response = await axios.get(`/sessions/`);

        return response.data;
    }

    async getSession(id: number): Promise<Session> {
        const response = await axios.get(`/sessions/${id}`);

        return response.data;
    }

    async getSessionWithChunks(id: number): Promise<Session> {
        const response = await axios.get(`/sessions/${id}/chunks`);

        return response.data;
    }

    async submitSelectedChunks(sessionId: number, selectedDocuments: any[]): Promise<void> {
        await axios.post(`/sessions/${sessionId}/submit`, selectedDocuments);
    }

    async resubmit(id: number, force = false): Promise<{ message: string; session_id: number; status: string }> {
        try {
            const response = await axios.post(`/sessions/${id}/resubmit`, null, {
                params: { force },
            });
            return response.data;
        } catch (error: any) {
            throw new Error(error.response?.data?.detail || 'An error occurred while resubmitting the session.');
        }
    }

    async remove(id: number): Promise<{ message: string; session_id: number }> {
        try {
            const response = await axios.delete(`/sessions/${id}`);
            return response.data;
        } catch (error: any) {
            throw new Error(error.response?.data?.detail || 'An error occurred while deleting the session.');
        }
    }

    async getSessionWithResult(id: number): Promise<SessionWithResultResponse> {
        const response = await axios.get(`/sessions/${id}/result`);

        return response.data;
    }

    async getBudget(): Promise<{ budget: number }> {
        const response = await axios.get(`/sessions/budget`);

        return response.data;
    }
}

export const sessionService = new SessionServiceImpl();
