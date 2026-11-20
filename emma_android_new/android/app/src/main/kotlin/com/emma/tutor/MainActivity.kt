package com.emma.tutor

import android.os.Bundle
import android.util.Log
import com.chaquo.python.Python
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import io.flutter.plugins.GeneratedPluginRegistrant

class MainActivity : FlutterActivity() {
    private val CHANNEL = "com.emma.tutor/python"
    private val TAG = "EmmaTutor"
    
    private var python: Python? = null
    
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        GeneratedPluginRegistrant.registerWith(flutterEngine)
        
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL).setMethodCallHandler { call, result ->
            when (call.method) {
                "initializePython" -> initializePython(result)
                "processMessage" -> processMessage(call, result)
                "getDevices" -> getDevices(result)
                "getNetworkStatus" -> getNetworkStatus(call, result)
                "wakeDevice" -> wakeDevice(call, result)
                "shutdownDevice" -> shutdownDevice(call, result)
                "getStudyPlan" -> getStudyPlan(result)
                "generateStudyPlan" -> generateStudyPlan(result)
                "webSearch" -> webSearch(call, result)
                else -> result.notImplemented()
            }
        }
    }
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        initializePython()
    }
    
    private fun initializePython() {
        try {
            if (!Python.isStarted()) {
                Python.start(this)
            }
            python = Python.getInstance()
            Log.i(TAG, "Python initialized successfully")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to initialize Python: ${e.message}")
        }
    }
    
    private fun initializePython(result: MethodChannel.Result) {
        initializePython()
        result.success("Python initialized")
    }
    
    private fun processMessage(call: MethodChannel.MethodCall, result: MethodChannel.Result) {
        val text = call.argument<String>("text") ?: ""
        val lang = call.argument<String>("lang") ?: "es"
        
        val python = Python.getInstance() ?: return
        try {
            val result = python.getModule("emma_bridge").callAttr("process_message", text, lang)
            result.success(result.toString())
        } catch (e: Exception) {
            result.error("ERROR", "Process message failed: ${e.message}", e)
        }
    }
    
    private fun getDevices(result: MethodChannel.Result) {
        val python = Python.getInstance() ?: return
        try {
            val result_str = python.getModule("emma_bridge").callAttr("get_devices")
            result.success(result_str.toString())
        } catch (e: Exception) {
            result.error("ERROR", "Get devices failed: ${e.message}", e)
        }
    }
    
    private fun getNetworkStatus(call: MethodChannel.MethodCall, result: MethodChannel.Result) {
        val device = call.argument<String>("device") ?: ""
        val python = Python.getInstance() ?: return
        try {
            val result_str = python.getModule("emma_bridge").callAttr("get_network_status", device)
            result.success(result_str.toString())
        } catch (e: Exception) {
            result.error("ERROR", "Get network status failed: ${e.message}", e)
        }
    }
    
    private fun wakeDevice(call: MethodChannel.MethodCall, result: MethodChannel.Result) {
        val name = call.argument<String>("name") ?: ""
        val python = Python.getInstance() ?: return
        try {
            val result_str = python.getModule("emma_bridge").callAttr("wake_device", name)
            result.success(result_str.toString())
        } catch (e: Exception) {
            result.error("ERROR", "Wake device failed: ${e.message}", e)
        }
    }
    
    private fun shutdownDevice(call: MethodChannel.MethodCall, result: MethodChannel.Result) {
        val name = call.argument<String>("name") ?: ""
        val python = Python.getInstance() ?: return
        try {
            val result_str = python.getModule("emma_bridge").callAttr("shutdown_device", name)
            result.success(result_str.toString())
        } catch (e: Exception) {
            result.error("ERROR", "Shutdown device failed: ${e.message}", e)
        }
    }
    
    private fun getStudyPlan(result: MethodChannel.Result) {
        val python = Python.getInstance() ?: return
        try {
            val result_str = python.getModule("emma_bridge").callAttr("get_study_plan")
            result.success(result_str.toString())
        } catch (e: Exception) {
            result.error("ERROR", "Get study plan failed: ${e.message}", e)
        }
    }
    
    private fun generateStudyPlan(result: MethodChannel.Result) {
        val python = Python.getInstance() ?: return
        try {
            val result_str = python.getModule("emma_bridge").callAttr("generate_study_plan")
            result.success(result_str.toString())
        } catch (e: Exception) {
            result.error("ERROR", "Generate study plan failed: ${e.message}", e)
        }
    }
    
    private fun webSearch(call: MethodChannel.MethodCall, result: MethodChannel.Result) {
        val query = call.argument<String>("query") ?: ""
        val python = Python.getInstance() ?: return
        try {
            val result_str = python.getModule("emma_bridge").callAttr("web_search", query)
            result.success(result_str.toString())
        } catch (e: Exception) {
            result.error("ERROR", "Web search failed: ${e.message}", e)
        }
    }
}