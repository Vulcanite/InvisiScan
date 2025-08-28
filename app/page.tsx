"use client"

import type React from "react"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Upload, X, CheckCircle, AlertCircle, Info, Download } from "lucide-react"

interface ProcessingData {
  original_filename: string;
  image_size: {
    width: number;
    height: number;
  };
  file_size: number;
  format: string;
  mode: string;
  processing_status: string;
}

interface ApiResponse {
  message: string;
  data: ProcessingData;
  processed_image: {
    base64: string;
    content_type: string;
  };
}

export default function ImageUploadPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState<"idle" | "success" | "error">("idle")
  const [preview, setPreview] = useState<string | null>(null)
  const [processedData, setProcessedData] = useState<ProcessingData | null>(null)
  const [processedImage, setProcessedImage] = useState<string | null>(null)

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      setSelectedFile(file)
      setUploadStatus("idle")
      setProcessedData(null)
      setProcessedImage(null)

      // Create preview
      const reader = new FileReader()
      reader.onload = (e) => {
        setPreview(e.target?.result as string)
      }
      reader.readAsDataURL(file)
    }
  }

  const handleUpload = async () => {
    if (!selectedFile) return

    setUploading(true)
    setUploadStatus("idle")

    try {
      const formData = new FormData()
      formData.append("image", selectedFile)

      const response = await fetch("http://localhost:8000/api/upload", {
        method: "POST",
        body: formData,
      })

      if (response.ok) {
        const result: ApiResponse = await response.json()
        setUploadStatus("success")
        setProcessedData(result.data)
        setProcessedImage(`data:${result.processed_image.content_type};base64,${result.processed_image.base64}`)
      } else {
        setUploadStatus("error")
      }
    } catch (error) {
      console.error("Upload failed:", error)
      setUploadStatus("error")
    } finally {
      setUploading(false)
    }
  }

  const handleDownload = () => {
    if (!processedImage || !processedData) return

    // Create a temporary anchor element to trigger download
    const link = document.createElement('a')
    link.href = processedImage
    
    // Generate filename for the processed image
    const originalName = processedData.original_filename
    const nameWithoutExt = originalName.substring(0, originalName.lastIndexOf('.')) || originalName
    const extension = processedData.format.toLowerCase()
    const downloadFilename = `${nameWithoutExt}_processed.${extension}`
    
    link.download = downloadFilename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const clearSelection = () => {
    setSelectedFile(null)
    setPreview(null)
    setUploadStatus("idle")
    setProcessedData(null)
    setProcessedImage(null)
  }

  return (
    <div className="min-h-screen bg-background p-4">
      <div className="max-w-4xl mx-auto mt-8">
        <div className="text-center mb-6">
          <h1 className="text-3xl font-bold text-foreground">Privacy First!</h1>
        </div>
        
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Upload Card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Upload className="h-5 w-5" />
                Image Upload
              </CardTitle>
              <CardDescription>Select an image file to upload to the backend</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* File Input */}
              <div className="space-y-2">
                <input type="file" accept="image/*" onChange={handleFileSelect} className="hidden" id="file-input" />
                <label
                  htmlFor="file-input"
                  className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-border rounded-lg cursor-pointer hover:bg-muted/50 transition-colors"
                >
                  <Upload className="h-8 w-8 text-muted-foreground mb-2" />
                  <span className="text-sm text-muted-foreground">Click to select an image</span>
                </label>
              </div>

              {/* Preview */}
              {preview && (
                <div className="relative">
                  <img
                    src={preview}
                    alt="Preview"
                    className="w-full h-48 object-cover rounded-lg"
                  />
                  <Button variant="destructive" size="sm" className="absolute top-2 right-2" onClick={clearSelection}>
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              )}

              {/* File Info */}
              {selectedFile && (
                <div className="text-sm text-muted-foreground">
                  <p>File: {selectedFile.name}</p>
                  <p>Size: {(selectedFile.size / 1024 / 1024).toFixed(2)} MB</p>
                </div>
              )}

              {/* Upload Button */}
              <Button onClick={handleUpload} disabled={!selectedFile || uploading} className="w-full">
                {uploading ? "Processing..." : "Upload Image"}
              </Button>

              {/* Status Messages */}
              {uploadStatus === "success" && (
                <div className="flex items-center gap-2 text-green-600">
                  <CheckCircle className="h-4 w-4" />
                  <span className="text-sm">Upload successful!</span>
                </div>
              )}

              {uploadStatus === "error" && (
                <div className="flex items-center gap-2 text-red-600">
                  <AlertCircle className="h-4 w-4" />
                  <span className="text-sm">Upload failed. Please try again.</span>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Results Card */}
          {(processedData || processedImage) && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Info className="h-5 w-5" />
                  Processing Results
                </CardTitle>
                <CardDescription>Backend processing information and processed image</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Processed Image */}
                {processedImage && (
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-sm font-medium">Processed Image:</h3>
                      <Button 
                        onClick={handleDownload} 
                        variant="outline" 
                        size="sm"
                        className="flex items-center gap-2"
                      >
                        <Download className="h-4 w-4" />
                        Download
                      </Button>
                    </div>
                    <img
                      src={processedImage}
                      alt="Processed"
                      className="w-full h-48 object-cover rounded-lg border"
                    />
                  </div>
                )}

                {/* Processing Data */}
                {processedData && (
                  <div className="space-y-2">
                    <h3 className="text-sm font-medium">Processing Information:</h3>
                    <div className="bg-muted p-3 rounded-lg text-sm space-y-1">
                      <p><span className="font-medium">Filename:</span> {processedData.original_filename}</p>
                      <p><span className="font-medium">Dimensions:</span> {processedData.image_size.width} × {processedData.image_size.height}</p>
                      <p><span className="font-medium">File Size:</span> {(processedData.file_size / 1024 / 1024).toFixed(2)} MB</p>
                      <p><span className="font-medium">Format:</span> {processedData.format}</p>
                      <p><span className="font-medium">Color Mode:</span> {processedData.mode}</p>
                      <p><span className="font-medium">Status:</span> <span className="text-green-600 capitalize">{processedData.processing_status}</span></p>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}