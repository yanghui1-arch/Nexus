import { apiRequest, buildApiPath } from '@/api/client';
import type {
  ApiFeature,
  ApiFeatureItemRetryTaskRequest,
  ApiFeatureItemRetryTaskResponse,
  ApiFeatureStatus,
  ApiProductProposal,
  ApiProductProposalStatus,
  ApiProductProposalStatusUpdateRequest,
} from '@/api/types';

export type ListProductProposalsParams = {
  status?: ApiProductProposalStatus;
  project?: string;
  repo?: string;
  limit?: number;
};

export type ListProductFeaturesParams = {
  status?: ApiFeatureStatus;
  project?: string;
  limit?: number;
};

export function listProductProposals(
  params: ListProductProposalsParams = {},
): Promise<ApiProductProposal[]> {
  return apiRequest<ApiProductProposal[]>(buildApiPath('/v1/product/proposals', params));
}

export function updateProductProposalStatus(
  proposalId: string,
  payload: ApiProductProposalStatusUpdateRequest,
): Promise<ApiProductProposal> {
  return apiRequest<ApiProductProposal>(`/v1/product/proposals/${proposalId}/status`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function retryProductProposalPlanning(
  proposalId: string,
): Promise<ApiProductProposal> {
  return apiRequest<ApiProductProposal>(`/v1/product/proposals/${proposalId}/retry-planning`, {
    method: 'POST',
  });
}

export function retryProductFeatureItemTask(
  featureItemId: string,
  payload: ApiFeatureItemRetryTaskRequest = {},
): Promise<ApiFeatureItemRetryTaskResponse> {
  return apiRequest<ApiFeatureItemRetryTaskResponse>(`/v1/product/feature-items/${featureItemId}/retry-task`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listProductFeatures(
  params: ListProductFeaturesParams = {},
): Promise<ApiFeature[]> {
  return apiRequest<ApiFeature[]>(buildApiPath('/v1/product/features', params));
}

export function getProductFeature(featureId: string): Promise<ApiFeature> {
  return apiRequest<ApiFeature>(`/v1/product/features/${featureId}`);
}
