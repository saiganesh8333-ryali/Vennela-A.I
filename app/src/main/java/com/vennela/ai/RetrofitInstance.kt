package com.vennela.ai

import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object RetrofitInstance {

    private val BASE_URL = AgentConfig.BACKEND_REST_BASE_URL

    private val logging = HttpLoggingInterceptor().apply {
        level = HttpLoggingInterceptor.Level.BODY
    }

    private val client = OkHttpClient.Builder()
        .connectTimeout(150, TimeUnit.SECONDS)
        .readTimeout(150, TimeUnit.SECONDS)
        .writeTimeout(150, TimeUnit.SECONDS)
        .addInterceptor(logging)
        .addInterceptor { chain ->
            val builder = chain.request().newBuilder()
                .header("User-Agent", "VennelaAI-Enterprise")
                .header("Accept", "application/json")
                .header("X-Vennela-Core", "v2.5")

            val bearerHeader = AgentConfig.getBearerHeader()
            if (bearerHeader != null) {
                builder.header("Authorization", bearerHeader)
            }

            val request = builder.build()
            chain.proceed(request)
        }
        .build()

    val api: ApiService by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ApiService::class.java)
    }
}
