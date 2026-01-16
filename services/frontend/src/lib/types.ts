// Type definitions for TaskManager frontend

export interface User {
	id: number;
	username: string;
	email: string;
	created_at: string;
}

export interface Todo {
	id: number;
	project_id: number | null;
	user_id: number;
	title: string;
	description: string | null;
	priority: 'low' | 'medium' | 'high' | 'urgent';
	status: 'pending' | 'in_progress' | 'completed' | 'cancelled';
	due_date: string | null;
	completed_date: string | null;
	estimated_hours: number | null;
	actual_hours: number | null;
	tags: string[];
	context: string | null;
	created_at: string;
	updated_at: string;
	project_name?: string;
	project_color?: string;
}

export interface Project {
	id: number;
	user_id: number;
	name: string;
	description: string | null;
	color: string;
	created_at: string;
	updated_at: string;
}

export interface TodoFilters {
	status?: string;
	project_id?: number;
	priority?: string;
	start_date?: string;
	end_date?: string;
}

export interface TodoCreate {
	title: string;
	description?: string;
	priority?: string;
	status?: string;
	due_date?: string;
	estimated_hours?: number;
	tags?: string[];
	context?: string;
	project_id?: number;
}

export interface TodoUpdate extends Partial<TodoCreate> {
	actual_hours?: number;
	completed_date?: string;
}

export interface ProjectCreate {
	name: string;
	description?: string;
	color: string;
}

export interface ProjectUpdate extends Partial<ProjectCreate> {}

export interface OAuthClient {
	id: number;
	client_id: string;
	name: string;
	redirect_uris: string[];
	grant_types: string[];
	scopes: string[];
	is_active: boolean;
	is_public: boolean;
	created_at: string;
}

export interface ApiResponse<T> {
	data?: T;
	tasks?: T;
	meta?: {
		count: number;
	};
	error?: {
		code: string;
		message: string;
		details?: Record<string, unknown>;
	};
}
