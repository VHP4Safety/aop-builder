import {User} from "./User.ts";
import {Token} from "./Token.ts";

export interface Auth
{
    user: User,
    token: Token
}