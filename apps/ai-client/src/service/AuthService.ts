import {Auth} from "../models/Auth.ts";
import {User} from "../models/User.ts";

export interface AuthService
{
    login(username: string, password: string): Promise<Auth>
    register(username: string, password: string): Promise<Auth>
    profile(): Promise<User>
    logout(): Promise<void>;
}