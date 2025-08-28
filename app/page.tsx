"use client"

import type React from "react"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Upload, X, CheckCircle, AlertCircle } from "lucide-react"

export default function ImageUploadPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState<"idle" | "success" | "error">("idle")
  const [preview, setPreview] = useState<string | null>(null)

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      setSelectedFile(file)
      setUploadStatus("idle")

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

      const response = await fetch("/api/upload", {
        method: "POST",
        body: formData,
      })

      if (response.ok) {
        setUploadStatus("success")
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

  const clearSelection = () => {
    setSelectedFile(null)
    setPreview(null)
    setUploadStatus("idle")
  }

  return (
    <div className="min-h-screen bg-background p-4">
      <div className="max-w-md mx-auto mt-8">
        <div className="text-center mb-6">
          <h1 className="text-3xl font-bold text-foreground">Privacy First!</h1>
        </div>
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
                  src={preview || "/placeholder.svg"}
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
              {uploading ? "Uploading..." : "Upload Image"}
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
      </div>
    </div>
  )
}
