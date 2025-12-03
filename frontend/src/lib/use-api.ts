'use client';

import { useState, useCallback } from 'react';
import { useToast } from './toast';
import { APIError } from './api';

/**
 * API Response State
 */
interface APIState<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
}

/**
 * Options for useAPI hook
 */
interface UseAPIOptions {
  showErrorToast?: boolean;
  showSuccessToast?: boolean;
  successMessage?: string;
  errorMessage?: string;
}

/**
 * Hook for making API calls with automatic error handling and toast notifications
 * 
 * @example
 * ```tsx
 * const { execute, loading, error, data } = useAPI(getRenewals, {
 *   showErrorToast: true,
 *   showSuccessToast: true,
 *   successMessage: 'Renewals loaded successfully',
 * });
 * 
 * // Call the API
 * const result = await execute({ status: 'active' });
 * ```
 */
export function useAPI<TArgs extends unknown[], TResult>(
  apiFunction: (...args: TArgs) => Promise<TResult>,
  options: UseAPIOptions = {},
) {
  const {
    showErrorToast = true,
    showSuccessToast = false,
    successMessage,
    errorMessage,
  } = options;

  const [state, setState] = useState<APIState<TResult>>({
    data: null,
    loading: false,
    error: null,
  });

  const toast = useToast();

  const execute = useCallback(
    async (...args: TArgs): Promise<TResult | null> => {
      setState((prev) => ({ ...prev, loading: true, error: null }));

      try {
        const result = await apiFunction(...args);
        setState({ data: result, loading: false, error: null });

        if (showSuccessToast) {
          toast.success(successMessage || 'Operation completed successfully');
        }

        return result;
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Unknown error');
        setState({ data: null, loading: false, error });

        if (showErrorToast) {
          const message = getErrorMessage(error, errorMessage);
          toast.error(message);
        }

        return null;
      }
    },
    [apiFunction, showErrorToast, showSuccessToast, successMessage, errorMessage, toast],
  );

  const reset = useCallback(() => {
    setState({ data: null, loading: false, error: null });
  }, []);

  return {
    ...state,
    execute,
    reset,
  };
}

/**
 * Hook for handling async mutations with optimistic updates
 */
interface UseMutationOptions<TResult> extends UseAPIOptions {
  onSuccess?: (data: TResult) => void;
  onError?: (error: Error) => void;
}

export function useMutation<TArgs extends unknown[], TResult>(
  mutationFn: (...args: TArgs) => Promise<TResult>,
  options: UseMutationOptions<TResult> = {},
) {
  const {
    showErrorToast = true,
    showSuccessToast = true,
    successMessage,
    errorMessage,
    onSuccess,
    onError,
  } = options;

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const toast = useToast();

  const mutate = useCallback(
    async (...args: TArgs): Promise<TResult | null> => {
      setLoading(true);
      setError(null);

      try {
        const result = await mutationFn(...args);
        setLoading(false);

        if (showSuccessToast) {
          toast.success(successMessage || 'Changes saved successfully');
        }

        onSuccess?.(result);
        return result;
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Unknown error');
        setLoading(false);
        setError(error);

        if (showErrorToast) {
          const message = getErrorMessage(error, errorMessage);
          toast.error(message);
        }

        onError?.(error);
        return null;
      }
    },
    [mutationFn, showErrorToast, showSuccessToast, successMessage, errorMessage, onSuccess, onError, toast],
  );

  return { mutate, loading, error };
}

/**
 * Format API errors into user-friendly messages
 */
function getErrorMessage(error: Error, fallback?: string): string {
  if (fallback) {
    return fallback;
  }

  if (error instanceof APIError) {
    // Map common status codes to friendly messages
    switch (error.status) {
      case 400:
        return error.message || 'Invalid request. Please check your input.';
      case 401:
        return 'Your session has expired. Please sign in again.';
      case 403:
        return 'You do not have permission to perform this action.';
      case 404:
        return 'The requested resource was not found.';
      case 409:
        return error.message || 'This operation conflicts with existing data.';
      case 422:
        return error.message || 'The provided data is invalid.';
      case 429:
        return 'Too many requests. Please wait a moment and try again.';
      case 500:
        return 'An internal server error occurred. Please try again later.';
      case 502:
      case 503:
      case 504:
        return 'Service temporarily unavailable. Please try again later.';
      default:
        return error.message || 'An unexpected error occurred.';
    }
  }

  // Network errors
  if (error.name === 'TypeError' && error.message.includes('fetch')) {
    return 'Network error. Please check your internet connection.';
  }

  return error.message || 'An unexpected error occurred.';
}

/**
 * Global error handler for catching unhandled promise rejections
 * Call this once in your app entry point
 */
export function setupGlobalErrorHandlers(toast: ReturnType<typeof useToast>) {
  if (typeof window === 'undefined') return;

  // Handle unhandled promise rejections
  window.addEventListener('unhandledrejection', (event) => {
    console.error('Unhandled promise rejection:', event.reason);
    
    // Only show toast for user-visible errors
    if (event.reason instanceof APIError) {
      toast.error(getErrorMessage(event.reason));
    }
  });

  // Handle JavaScript errors
  window.addEventListener('error', (event) => {
    console.error('JavaScript error:', event.error);
    
    // Don't show toast for every JS error, just log them
    // In production, send to error monitoring service
  });
}

/**
 * Utility to handle async operations with error handling
 */
export async function handleAsync<T>(
  promise: Promise<T>,
  toast: ReturnType<typeof useToast>,
  options: {
    errorMessage?: string;
    successMessage?: string;
    showError?: boolean;
    showSuccess?: boolean;
  } = {},
): Promise<[T | null, Error | null]> {
  const { errorMessage, successMessage, showError = true, showSuccess = false } = options;

  try {
    const result = await promise;
    if (showSuccess && successMessage) {
      toast.success(successMessage);
    }
    return [result, null];
  } catch (err) {
    const error = err instanceof Error ? err : new Error('Unknown error');
    if (showError) {
      toast.error(getErrorMessage(error, errorMessage));
    }
    return [null, error];
  }
}

export { getErrorMessage };
