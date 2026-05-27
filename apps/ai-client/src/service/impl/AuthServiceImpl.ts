import axios from 'axios';
import {AuthService} from "../AuthService.ts";
import {Auth} from "../../models/Auth.ts";
import {User} from "../../models/User.ts";

export class AuthServiceImpl implements AuthService
{
    async login(username: string, password: string): Promise<Auth> {
        try {
            const response = await axios.post('/auth/login', {
                username,
                password,
            });

            return response.data;
        } catch (error: any) {
            throw new Error(error.response?.data?.detail || 'Er is een fout opgetreden tijdens het inloggen.');
        }
    }

    async register(username: string, password: string): Promise<Auth>
    {
        try {
            const response = await axios.post('/auth/register', { username, password })

            return response.data
        } catch (error: any) {
            throw new Error(error.response?.data?.detail || 'Er is een fout opgetreden tijdens het inloggen.');
        }
    }

    async profile(): Promise<User>
    {
        try {
            const response = await axios.get('/auth/profile')

            return response.data
        } catch (error: any) {
            throw new Error(error.response?.data?.detail || 'Er is een fout opgetreden tijdens het inloggen.');
        }
    }

    async logout(): Promise<void>
    {
        localStorage.clear()
        return Promise.resolve()
    }
}

export const authService = new AuthServiceImpl();