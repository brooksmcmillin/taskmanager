import { Auth } from '../../../lib/auth.js';
import { errors } from '../../../lib/errors.js';
import {
  validateUsername,
  validateEmail,
  validatePassword,
  validateAll,
} from '../../../lib/validators.js';
import { createdResponse } from '../../../lib/apiResponse.js';

export async function POST({ request }) {
  // Disable Registration for now
  return errors.validation('Registration is currently disabled').toResponse();

  try {
    const body = await request.json();

    // Validate all fields
    const validation = validateAll({
      username: validateUsername(body.username),
      email: validateEmail(body.email),
      password: validatePassword(body.password),
    });

    if (!validation.valid) {
      return validation.error.toResponse();
    }

    const { username, email, password } = validation.values;

    const result = await Auth.createUser(username, email, password);

    return createdResponse({
      message: 'User created successfully',
      userId: result.id,
    });
  } catch (error) {
    if (error.message.includes('already exists')) {
      return errors.userExists().toResponse();
    }
    return errors.validation(error.message).toResponse();
  }
}
