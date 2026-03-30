// AirflowApiClient.cs
// Async Unity HTTP client for the Eagle Ridge airflow planning backend.
//
// Usage:
//   var client = new AirflowApiClient("http://localhost:8000");
//   SiteOverlay overlay = await client.GetOverlayAsync();
//
// Requires Unity 2021.2+ (UnityWebRequest with async/await via Awaiter extension)
// and Newtonsoft.Json for Unity (com.unity.nuget.newtonsoft-json).

using System;
using System.Text;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.Networking;
using Newtonsoft.Json;
using EagleRidge.Airflow.Models;

namespace EagleRidge.Airflow.API
{
    /// <summary>Thrown when the backend returns a non-2xx HTTP status.</summary>
    public class AirflowApiException : Exception
    {
        public long StatusCode { get; }
        public string ResponseBody { get; }

        public AirflowApiException(long statusCode, string responseBody, string message)
            : base(message)
        {
            StatusCode = statusCode;
            ResponseBody = responseBody;
        }
    }

    /// <summary>Request body for POST /planning.</summary>
    [Serializable]
    public class PlanningRequest
    {
        public string site_id;
        public string target_date;      // ISO date YYYY-MM-DD, or null
        public string target_time_utc;  // HH:MM, or null
    }

    /// <summary>
    /// Typed async HTTP client for the paragliding airflow planning backend.
    ///
    /// All methods are async and safe to await from MonoBehaviour.Start()
    /// via StartCoroutine or an async void method.
    /// </summary>
    public class AirflowApiClient
    {
        private readonly string _baseUrl;
        private static readonly JsonSerializerSettings _jsonSettings = new JsonSerializerSettings
        {
            NullValueHandling = NullValueHandling.Ignore,
            MissingMemberHandling = MissingMemberHandling.Ignore,
        };

        /// <param name="baseUrl">Backend base URL, e.g. "http://localhost:8000".</param>
        public AirflowApiClient(string baseUrl = "http://localhost:8000")
        {
            _baseUrl = baseUrl.TrimEnd('/');
        }

        // ---------------------------------------------------------------------------
        // Public API methods
        // ---------------------------------------------------------------------------

        /// <summary>
        /// Fetch the latest site overlay (no session-specific filtering).
        /// Calls GET /unity/overlays.
        /// </summary>
        public async Task<SiteOverlay> GetOverlayAsync()
        {
            return await GetAsync<SiteOverlay>("/unity/overlays");
        }

        /// <summary>
        /// Fetch a session-specific overlay.
        /// Calls GET /unity/overlays/{sessionId}.
        /// </summary>
        public async Task<SiteOverlay> GetOverlayAsync(int sessionId)
        {
            return await GetAsync<SiteOverlay>($"/unity/overlays/{sessionId}");
        }

        /// <summary>
        /// Trigger a new planning session and return the negotiation result as a SiteOverlay.
        /// Calls POST /planning, then GET /unity/overlays/{sessionId}.
        /// </summary>
        public async Task<SiteOverlay> RunPlanningAndGetOverlayAsync(
            string siteId = "eagle_ridge",
            string targetDate = null,
            string targetTimeUtc = null)
        {
            var request = new PlanningRequest
            {
                site_id = siteId,
                target_date = targetDate,
                target_time_utc = targetTimeUtc,
            };

            // POST /planning returns a NegotiationResult with session_id
            var json = JsonConvert.SerializeObject(request, _jsonSettings);
            var planningResult = await PostAsync<NegotiationResult>("/planning", json);

            // Fetch the rendered Unity overlay for that session
            return await GetOverlayAsync(planningResult.session_id);
        }

        /// <summary>
        /// Check backend liveness and retrieve the configured site_id.
        /// Calls GET /health.
        /// </summary>
        public async Task<HealthResponse> CheckHealthAsync()
        {
            return await GetAsync<HealthResponse>("/health");
        }

        // ---------------------------------------------------------------------------
        // Internal HTTP helpers
        // ---------------------------------------------------------------------------

        private async Task<T> GetAsync<T>(string path)
        {
            var url = _baseUrl + path;
            using var request = UnityWebRequest.Get(url);
            request.SetRequestHeader("Accept", "application/json");

            var op = request.SendWebRequest();
            while (!op.isDone)
                await Task.Yield();

            EnsureSuccess(request, path);
            return Deserialise<T>(request.downloadHandler.text, path);
        }

        private async Task<T> PostAsync<T>(string path, string jsonBody)
        {
            var url = _baseUrl + path;
            var bodyBytes = Encoding.UTF8.GetBytes(jsonBody);

            using var request = new UnityWebRequest(url, "POST");
            request.uploadHandler = new UploadHandlerRaw(bodyBytes);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");
            request.SetRequestHeader("Accept", "application/json");

            var op = request.SendWebRequest();
            while (!op.isDone)
                await Task.Yield();

            EnsureSuccess(request, path);
            return Deserialise<T>(request.downloadHandler.text, path);
        }

        private static void EnsureSuccess(UnityWebRequest request, string path)
        {
            if (request.result != UnityWebRequest.Result.Success)
            {
                var body = request.downloadHandler?.text ?? string.Empty;
                throw new AirflowApiException(
                    request.responseCode,
                    body,
                    $"API error {request.responseCode} for {path}: {request.error}. Body: {body}"
                );
            }
        }

        private static T Deserialise<T>(string json, string path)
        {
            try
            {
                return JsonConvert.DeserializeObject<T>(json, _jsonSettings);
            }
            catch (Exception ex)
            {
                throw new AirflowApiException(
                    200,
                    json,
                    $"Failed to deserialise response from {path}: {ex.Message}"
                );
            }
        }
    }

    // ---------------------------------------------------------------------------
    // Helper response types
    // ---------------------------------------------------------------------------

    [Serializable]
    public class HealthResponse
    {
        public string status;
        public string site_id;
    }

    /// <summary>Minimal NegotiationResult shape used to extract session_id after POST /planning.</summary>
    [Serializable]
    public class NegotiationResult
    {
        public int session_id;
        public string advisory_disclaimer;
        public string uncertainty_summary;
    }
}
