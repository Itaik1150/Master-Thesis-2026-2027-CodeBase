import { CookieOptions, Request, Response } from 'express';
import { usersService } from '../services/users.service';
import { requestHandler } from '../utils/requestHandler';

const cookieConfig: CookieOptions = {
    httpOnly: true,
    sameSite: 'none',
    secure: true,
    maxAge: 24 * 60 * 60 * 1000,
};

class UsersController {
    createUser = requestHandler(
        async (req: Request, res: Response) => {
            const { userInfo, experimentId, fcmToken } = req.body;
            const { user, token } = await usersService.createUser(userInfo, experimentId, fcmToken);

            res.cookie('token', token, cookieConfig);
            res.status(200).send(user);
        },
        (req, res, error) => {
            if (error.code === 11000) {
                res.status(409).json({ message: 'User Already Exists' });
                return;
            }
            if (error.code === 403) {
                res.status(403).json({ message: 'Experiment Is Not Acive' });
                return;
            }
            res.status(500).json({ message: 'Error creating user' });
        },
    );

    login = requestHandler(
        async (req: Request, res: Response) => {
            const { username, userPassword, experimentId } = req.body;
            const { token, user } = await usersService.login(username, experimentId, userPassword);

            res.cookie('token', token, cookieConfig);
            res.status(200).send({ token, user });
        },
        (req, res, error) => {
            if (error.code === 401) {
                res.status(error.code).json({ message: error.message });
                return;
            }
            res.status(500).json({ message: 'Error creating user' });
        },
    );

    getActiveUser = requestHandler(async (req: Request, res: Response) => {
        if (!req.cookies || !req.cookies.token) {
            throw Object.assign(new Error('No token provided.'), { status: 401 });
        }

        const { token } = req.cookies;
        const { user, newToken } = await usersService.getActiveUser(token);

        res.cookie('token', newToken, cookieConfig);
        res.status(200).send(user);
    });

    logout = requestHandler(async (req: Request, res: Response) => {
        res.clearCookie('token', { httpOnly: true, sameSite: 'none', secure: true });
        res.status(200).send({ message: 'Logged out successfully' });
    });

    validateUserName = requestHandler(
        async (req, res) => {
            const username = req.query.username as string;
            const experimentId = req.query.experimentId as string;
            const user = await usersService.getUserByName(username, experimentId);
            if (user) {
                const error = new Error('User Already Exist');
                error['code'] = 409;
                throw error;
            }

            res.status(200).send(true);
        },
        (req, res, error) => {
            if (error.code === 409) {
                res.status(409).json({ message: 'User Already Exists' });
            }
        },
    );

    updateUsersAgent = requestHandler(async (req: Request, res: Response) => {
        const { agent } = req.body;
        await usersService.updateUsersAgent(agent);
        res.status(200).send();
    });

    updateFCMToken = requestHandler(
        async (req: Request, res: Response) => {
            const { userId, fcmToken } = req.body;
            
            if (!userId || !fcmToken) {
                const error = new Error('userId and fcmToken are required');
                error['code'] = 400;
                throw error;
            }

            const updatedUser = await usersService.updateFCMToken(userId, fcmToken);
            res.status(200).json({ 
                message: 'FCM token updated successfully',
                user: updatedUser 
            });
        },
        (req, res, error) => {
            if (error.code === 404) {
                res.status(404).json({ message: 'User not found' });
                return;
            }
            if (error.code === 400) {
                res.status(400).json({ message: error.message });
                return;
            }
            res.status(500).json({ message: 'Error updating FCM token' });
        },
    );

    registerDevice = requestHandler(
        async (req: Request, res: Response) => {
            const { userId, fcmToken, experimentId } = req.body;
            
            if (!userId || !fcmToken) {
                const error = new Error('userId and fcmToken are required');
                error['code'] = 400;
                throw error;
            }

            const updatedUser = await usersService.updateFCMToken(userId, fcmToken);
            res.status(200).json({ 
                message: 'Device registered successfully',
                user: updatedUser 
            });
        },
        (req, res, error) => {
            if (error.code === 404) {
                res.status(404).json({ message: 'User not found' });
                return;
            }
            if (error.code === 400) {
                res.status(400).json({ message: error.message });
                return;
            }
            res.status(500).json({ message: 'Error registering device' });
        },
    );
}

export const usersController = new UsersController();
