// 🔥 TEST FUNCTION - Add this to your Android Activity/Fragment
// Test the API call directly

fun testApiCall() {
    val apiService = RetrofitClient.getApiService()
    val repository = ChatRepository(apiService)

    lifecycleScope.launch {
        repository.sendMessage("test_user", "hi").collect { result ->
            when (result) {
                is ApiResult.Loading -> {
                    Log.d("TEST", "Loading...")
                }
                is ApiResult.Success -> {
                    Log.d("TEST", "SUCCESS: ${result.data.reply}")
                    Log.d("TEST", "Provider: ${result.data.provider}")
                    Log.d("TEST", "Latency: ${result.data.latencyMs}ms")
                }
                is ApiResult.Error -> {
                    Log.e("TEST", "ERROR: ${result.message}")
                    Log.e("TEST", "Code: ${result.code}")
                }
            }
        }
    }
}

// Call this function from a button click to test
// If you get "Method Not Allowed", check your @POST annotation</content>
<parameter name="filePath">d:\Vennela A.I\android_test_api_call.kt