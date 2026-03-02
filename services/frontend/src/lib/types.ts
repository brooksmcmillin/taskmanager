// Type definitions for TaskManager frontend

export interface User {
	id: number;
	email: string;
	is_admin: boolean;
	created_at: string;
}

export interface Attachment {
	id: number;
	todo_id: number;
	filename: string;
	content_type: string;
	file_size: number;
	created_at: string;
}

export interface Comment {
	id: number;
	todo_id: number;
	user_id: number;
	content: string;
	created_at: string;
	updated_at: string | null;
}

export interface CommentCreate {
	content: string;
}

export interface Subtask {
	id: number;
	title: string;
	description: string | null;
	priority: 'low' | 'medium' | 'high' | 'urgent';
	status: 'pending' | 'in_progress' | 'completed' | 'cancelled';
	due_date: string | null;
	deadline_type: DeadlineType;
	estimated_hours: number | null;
	actual_hours: number | null;
	position: number;
	created_at: string;
	updated_at: string | null;
}

export interface TaskDependency {
	id: number;
	title: string;
	status: 'pending' | 'in_progress' | 'completed' | 'cancelled';
	priority: 'low' | 'medium' | 'high' | 'urgent';
	due_date: string | null;
	project_id: number | null;
	project_name: string | null;
}

export interface ParentTask {
	id: number;
	title: string;
	status: 'pending' | 'in_progress' | 'completed' | 'cancelled';
	priority: 'low' | 'medium' | 'high' | 'urgent';
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
	deadline_type: DeadlineType;
	completed_date: string | null;
	estimated_hours: number | null;
	actual_hours: number | null;
	tags: string[];
	context: string | null;
	recurring_task_id: number | null;
	parent_id: number | null;
	parent_task?: ParentTask | null;
	position: number;
	subtasks: Subtask[];
	dependencies?: TaskDependency[];
	dependents?: TaskDependency[];
	attachments?: Attachment[];
	comments?: Comment[];
	created_at: string;
	updated_at: string;
	deleted_at?: string | null;
	project_name?: string;
	project_color?: string;
}

export interface ProjectStats {
	total_tasks: number;
	completed_tasks: number;
	pending_tasks: number;
	in_progress_tasks: number;
	cancelled_tasks: number;
	completion_percentage: number;
	total_estimated_hours: number | null;
	total_actual_hours: number | null;
	overdue_tasks: number;
}

export interface Project {
	id: number;
	user_id: number;
	name: string;
	description: string | null;
	color: string;
	position: number;
	is_active: boolean;
	show_on_calendar: boolean;
	archived_at: string | null;
	created_at: string;
	updated_at: string;
	stats?: ProjectStats;
}

export interface TodoFilters {
	status?: string;
	project_id?: number;
	priority?: string;
	deadline_type?: DeadlineType;
	start_date?: string;
	end_date?: string;
	no_due_date?: boolean;
	include_subtasks?: boolean;
	order_by?: string;
	exclude_no_calendar?: boolean;
}

export interface TodoCreate {
	title: string;
	description?: string;
	priority?: string;
	status?: string;
	due_date?: string;
	deadline_type?: DeadlineType;
	estimated_hours?: number;
	tags?: string[];
	context?: string;
	project_id?: number;
	parent_id?: number;
	position?: number;
}

export interface SubtaskCreate {
	title: string;
	description?: string;
	priority?: string;
	due_date?: string;
	estimated_hours?: number;
}

export interface TodoUpdate extends Partial<TodoCreate> {
	actual_hours?: number;
	completed_date?: string;
}

export interface ProjectCreate {
	name: string;
	description?: string;
	color: string;
	position?: number;
	show_on_calendar?: boolean;
}

export interface ProjectUpdate extends Partial<ProjectCreate> {
	is_active?: boolean;
	// Note: archived_at is not settable via update - use archive/unarchive endpoints
}

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

export interface RegistrationCode {
	id: number;
	code: string;
	max_uses: number;
	current_uses: number;
	is_active: boolean;
	expires_at: string | null;
	created_at: string;
	created_by_email: string | null;
}

export type DeadlineType = 'flexible' | 'preferred' | 'firm' | 'hard';

export type ArticleRating = 'good' | 'bad' | 'not_interested';

export interface Article {
	id: number;
	title: string;
	url: string;
	summary: string | null;
	author: string | null;
	published_at: string | null;
	keywords: string[];
	feed_source_name: string;
	is_read: boolean;
	rating: ArticleRating | null;
	read_at: string | null;
	is_bookmarked: boolean;
	bookmarked_at: string | null;
}

export interface ReadingStats {
	streak_days: number;
	articles_read_today: number;
	articles_read_this_week: number;
	total_articles_read: number;
	total_bookmarked: number;
}

export type FeedType = 'paper' | 'article';

export interface FeedSource {
	id: number;
	name: string;
	url: string;
	description: string | null;
	type: FeedType;
	is_active: boolean;
	is_featured: boolean;
	fetch_interval_hours: number;
	last_fetched_at: string | null;
	quality_score: number;
	created_at: string;
}

export interface FeedSourceCreate {
	name: string;
	url: string;
	description?: string;
	type?: FeedType;
	is_active?: boolean;
	is_featured?: boolean;
	fetch_interval_hours?: number;
}

export interface FeedSourceUpdate extends Partial<FeedSourceCreate> {}

export type Frequency = 'daily' | 'weekly' | 'monthly' | 'yearly';

export interface RecurringTask {
	id: number;
	title: string;
	frequency: Frequency;
	interval_value: number;
	weekdays: number[] | null;
	day_of_month: number | null;
	start_date: string;
	end_date: string | null;
	next_due_date: string;
	project_id: number | null;
	description: string | null;
	priority: 'low' | 'medium' | 'high' | 'urgent';
	estimated_hours: number | null;
	tags: string[];
	context: string | null;
	skip_missed: boolean;
	is_active: boolean;
	created_at: string;
	updated_at: string | null;
}

export interface RecurringTaskCreate {
	title: string;
	frequency: Frequency;
	start_date: string;
	interval_value?: number;
	weekdays?: number[];
	day_of_month?: number;
	end_date?: string;
	project_id?: number;
	description?: string;
	priority?: string;
	estimated_hours?: number;
	tags?: string[];
	context?: string;
	skip_missed?: boolean;
}

export interface RecurringTaskUpdate extends Partial<RecurringTaskCreate> {
	is_active?: boolean;
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

export interface ApiKey {
	id: number;
	name: string;
	key_prefix: string;
	is_active: boolean;
	expires_at: string | null;
	last_used_at: string | null;
	created_at: string;
}

export interface ApiKeyCreate {
	name: string;
	expires_at?: string;
}

export interface ApiKeyCreateResponse extends ApiKey {
	key: string;
}

// Wiki types
export interface WikiPageAncestor {
	id: number;
	title: string;
	slug: string;
}

export interface WikiPageChildSummary {
	id: number;
	title: string;
	slug: string;
	child_count: number;
}

export interface WikiTreeNode {
	id: number;
	title: string;
	slug: string;
	tags: string[];
	updated_at: string | null;
	children: WikiTreeNode[];
}

export interface WikiPage {
	id: number;
	title: string;
	slug: string;
	content: string;
	parent_id: number | null;
	tags: string[];
	ancestors: WikiPageAncestor[];
	children: WikiPageChildSummary[];
	created_at: string;
	updated_at: string | null;
}

export interface WikiPageSummary {
	id: number;
	title: string;
	slug: string;
	parent_id: number | null;
	tags: string[];
	created_at: string;
	updated_at: string | null;
}

export interface WikiPageCreate {
	title: string;
	content?: string;
	slug?: string;
	parent_id?: number;
	tags?: string[];
}

export interface WikiPageUpdate {
	title?: string;
	content?: string;
	slug?: string;
	parent_id?: number;
	remove_parent?: boolean;
	tags?: string[];
}

export interface WikiLinkedTodo {
	id: number;
	title: string;
	status: string;
	priority: string;
	due_date: string | null;
}

// Snippets
export interface Snippet {
	id: number;
	category: string;
	title: string;
	content: string;
	snippet_date: string;
	tags: string[];
	created_at: string;
	updated_at: string | null;
}

export interface SnippetSummary {
	id: number;
	category: string;
	title: string;
	snippet_date: string;
	tags: string[];
	created_at: string;
	updated_at: string | null;
}

export interface SnippetCreate {
	category: string;
	title: string;
	content?: string;
	snippet_date?: string;
	tags?: string[];
}

export interface SnippetUpdate {
	category?: string;
	title?: string;
	content?: string;
	snippet_date?: string;
	tags?: string[];
}

export interface CategoryCount {
	category: string;
	count: number;
}
