"use client"

import type React from "react"
import { useState, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Upload, X, CheckCircle, AlertCircle, Info, Download, Paperclip, Eye, Shield, FileText, ImageIcon } from "lucide-react"
import { motion, AnimatePresence } from "framer-motion"
import mammoth from "mammoth"

interface ProcessingData {
  original_filename?: string;
  image_size?: {
    width: number;
    height: number;
  };
  file_size?: number;
  format?: string;
  mode?: string;
  processing_status: string;
  input_type: 'image' | 'text';
}

interface ApiResponse {
  message: string;
  data: ProcessingData;
  processed_image?: {
    base64: string;
    content_type: string;
  };
  redacted_text?: string;
  analysis_summary?: string;
}

type TabType = 'text' | 'image';

export default function DataScanPage() {
  const [activeTab, setActiveTab] = useState<TabType>('text')
  
  // Text-specific state
  const [textInput, setTextInput] = useState<string>("")
  const [textFile, setTextFile] = useState<File | null>(null)
  const [textUploading, setTextUploading] = useState(false)
  const [textStatus, setTextStatus] = useState<"idle" | "success" | "error">("idle")
  const [redactedText, setRedactedText] = useState<string | null>(null)
  const [textProcessedData, setTextProcessedData] = useState<ProcessingData | null>(null)
  const [textMessage, setTextMessage] = useState<string | null>(null)
  
  // Image-specific state
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  const [imageUploading, setImageUploading] = useState(false)
  const [imageStatus, setImageStatus] = useState<"idle" | "success" | "error">("idle")
  const [processedImage, setProcessedImage] = useState<string | null>(null)
  const [imageProcessedData, setImageProcessedData] = useState<ProcessingData | null>(null)
  const [imageMessage, setImageMessage] = useState<string | null>(null)
  
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const textFileInputRef = useRef<HTMLInputElement>(null)
  const imageFileInputRef = useRef<HTMLInputElement>(null)

  const isWordFile = (file: File) => {
    return file.type === "application/vnd.openxmlformats-officedocument.wordprocessingml.document" || 
           file.type === "application/msword"
  }

  const isTextFile = (file: File) => {
    return file.type.startsWith("text/") || file.name.toLowerCase().endsWith(".txt")
  }

  const isImageFile = (file: File) => {
    return file.type.startsWith('image/')
  }

  // Text processing functions
  const resetTextState = () => {
    setTextStatus("idle")
    setTextProcessedData(null)
    setRedactedText(null)
    setTextMessage(null)
  }

  const handleTextFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    
    resetTextState()
    
    if (isWordFile(file)) {
      const arrayBuffer = await file.arrayBuffer()
      const { value } = await mammoth.extractRawText({ arrayBuffer })
      setTextInput(value.trim())
      setTextFile(file)
      if (textareaRef.current) {
        textareaRef.current.value = value.trim()
      }
    } else if (isTextFile(file)) {
      const reader = new FileReader()
      reader.onload = (event) => {
        const textContent = (event.target?.result as string)?.trim()
        if (textContent) {
          setTextInput(textContent)
          setTextFile(file)
          if (textareaRef.current) {
            textareaRef.current.value = textContent
          }
        }
      }
      reader.readAsText(file)
    } else {
      alert("Please select a text file (.txt) or Word document (.doc, .docx)")
      event.target.value = ""
    }
  }

  const handleTextChange = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    const text = event.target.value
    setTextInput(text)
    
    if (text.trim()) {
      resetTextState()
      // Clear file input if user is typing
      if (textFileInputRef.current) {
        textFileInputRef.current.value = ""
      }
      setTextFile(null)
    }
  }

  const handleTextScan = async () => {
    if (!textInput.trim()) return

    setTextUploading(true)
    setTextStatus("idle")

    try {
      const formData = new FormData()
      formData.append("text_input", textInput.trim())

      const response = await fetch("http://localhost:8000/api/scan", {
        method: "POST",
        body: formData,
      })

      if (response.ok) {
        const result: ApiResponse = await response.json()
        setTextStatus("success")
        setTextProcessedData(result.data)
        setRedactedText(result.redacted_text || null)
        setTextMessage(result.message)
      } else {
        setTextStatus("error")
      }
    } catch (error) {
      console.error("Text scan failed:", error)
      setTextStatus("error")
    } finally {
      setTextUploading(false)
    }
  }

  const clearTextInput = () => {
    setTextInput("")
    setTextFile(null)
    setRedactedText(null)
    setTextProcessedData(null)
    setTextMessage(null)
    setTextStatus("idle")
    
    if (textareaRef.current) {
      textareaRef.current.value = ""
    }
    if (textFileInputRef.current) {
      textFileInputRef.current.value = ""
    }
  }

  const downloadRedactedText = () => {
    if (redactedText) {
      const blob = new Blob([redactedText], { type: 'text/plain' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = textFile ? `${textFile.name}_redacted.txt` : 'redacted_text.txt'
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
    }
  }

  // Image processing functions
  const resetImageState = () => {
    setImageStatus("idle")
    setImageProcessedData(null)
    setProcessedImage(null)
    setImageMessage(null)
  }

  const handleImageFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    
    if (isImageFile(file)) {
      setImageFile(file)
      resetImageState()

      // Create image preview
      const reader = new FileReader()
      reader.onload = (e) => {
        setImagePreview(e.target?.result as string)
      }
      reader.readAsDataURL(file)
    } else {
      alert("Please select an image file")
      event.target.value = ""
    }
  }

  const handleImagePaste = async (event: React.ClipboardEvent) => {
    const items = event.clipboardData?.items
    
    if (items) {
      for (let i = 0; i < items.length; i++) {
        const item = items[i]
        
        if (item.type.startsWith('image/')) {
          event.preventDefault()
          const blob = item.getAsFile()

          if (blob) {
            const file = new File([blob], "pasted-image.png", { type: blob.type })
            setImageFile(file)
            resetImageState()

            const reader = new FileReader()
            reader.onload = (e) => {
              setImagePreview(e.target?.result as string)
            }
            reader.readAsDataURL(file)
          }
          return
        }
      }
    }
  }

  const handleImageScan = async () => {
    if (!imageFile) return

    setImageUploading(true)
    setImageStatus("idle")

    try {
      const formData = new FormData()
      formData.append("image", imageFile, imageFile.name)

      const response = await fetch("http://localhost:8000/api/scan", {
        method: "POST",
        body: formData,
      })

      if (response.ok) {
        const result: ApiResponse = await response.json()
        setImageStatus("success")
        setImageProcessedData(result.data)
        setImageMessage(result.message)

        if (result.processed_image) {
          setProcessedImage(`data:${result.processed_image.content_type};base64,${result.processed_image.base64}`)
        }
      } else {
        setImageStatus("error")
      }
    } catch (error) {
      console.error("Image scan failed:", error)
      setImageStatus("error")
    } finally {
      setImageUploading(false)
    }
  }

  const clearImageInput = () => {
    setImageFile(null)
    setImagePreview(null)
    setProcessedImage(null)
    setImageProcessedData(null)
    setImageMessage(null)
    setImageStatus("idle")
    
    if (imageFileInputRef.current) {
      imageFileInputRef.current.value = ""
    }
  }

  const downloadProcessedImage = () => {
    if (processedImage && imageProcessedData) {
      const link = document.createElement('a')
      link.href = processedImage
      
      const originalName = imageProcessedData.original_filename || 'image'
      const nameWithoutExt = originalName.substring(0, originalName.lastIndexOf('.')) || originalName
      const extension = imageProcessedData.format?.toLowerCase() || 'jpg'
      const downloadFilename = `${nameWithoutExt}_processed.${extension}`
      
      link.download = downloadFilename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    }
  }

  return (
    <div className="min-h-screen bg-background p-4">
      <div className="max-w-6xl mx-auto mt-8">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-foreground mb-2">Privacy First!</h1>
          <p className="text-lg text-muted-foreground">Protect your sensitive information with AI-powered detection and masking</p>
        </div>
        
        {/* Tab Navigation */}
        <div className="flex justify-center mb-8">
          <div className="inline-flex rounded-lg border bg-muted p-1">
            <button
              onClick={() => setActiveTab('text')}
              className={`inline-flex items-center gap-2 rounded-md px-6 py-3 text-sm font-medium transition-all ${
                activeTab === 'text'
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <FileText className="h-4 w-4" />
              PII Detection & Masking
            </button>
            <button
              onClick={() => setActiveTab('image')}
              className={`inline-flex items-center gap-2 rounded-md px-6 py-3 text-sm font-medium transition-all ${
                activeTab === 'image'
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <ImageIcon className="h-4 w-4" />
              Visual Privacy Protection
            </button>
          </div>
        </div>

        <AnimatePresence mode="wait">
          {activeTab === 'text' && (
            <motion.div
              key="text-tab"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.3 }}
            >
              <div className={`grid gap-6 ${redactedText || textProcessedData ? "grid-cols-1 lg:grid-cols-2" : "grid-cols-1 place-items-center"}`}>
                {/* Text Input Card */}
                <Card className={`${redactedText || textProcessedData ? "" : "max-w-2xl w-full"}`}>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Shield className="h-5 w-5" />
                      PII Detection & Masking
                    </CardTitle>
                    <CardDescription>
                      Detect and mask personally identifiable information in your text documents
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {/* File Input */}
                    <input 
                      ref={textFileInputRef}
                      type="file" 
                      accept=".txt,.doc,.docx"
                      onChange={handleTextFileSelect} 
                      className="hidden" 
                      id="text-file-input" 
                    />
                    
                    {/* Text Input Area */}
                    <div className="space-y-3">
                      <div className="relative">
                        <textarea
                          ref={textareaRef}
                          onChange={handleTextChange}
                          placeholder="Enter your text here to scan for PII (names, emails, phone numbers, addresses, etc.)..."
                          className="w-full h-48 p-4 border border-border rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="absolute bottom-2 right-2 h-8 w-8 p-0"
                          onClick={() => textFileInputRef.current?.click()}
                          title="Upload text file"
                        >
                          <Paperclip className="h-4 w-4" />
                        </Button>
                      </div>
                      
                      {textFile && (
                        <div className="flex items-center justify-between p-2 bg-muted rounded-lg">
                          <div className="flex items-center gap-2">
                            <FileText className="h-4 w-4" />
                            <span className="text-sm">{textFile.name}</span>
                          </div>
                          <Button variant="ghost" size="sm" onClick={() => {
                            setTextFile(null)
                            if (textFileInputRef.current) textFileInputRef.current.value = ""
                          }}>
                            <X className="h-4 w-4" />
                          </Button>
                        </div>
                      )}
                      
                      <p className="text-xs text-muted-foreground">
                        💡 Supported formats: Plain text, Word documents (.doc, .docx)
                      </p>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex gap-2">
                      <Button 
                        onClick={handleTextScan} 
                        disabled={!textInput.trim() || textUploading} 
                        className="flex-1"
                      >
                        <Shield className="h-4 w-4 mr-2" />
                        {textUploading ? "Scanning..." : "Scan for PII"}
                      </Button>
                      
                      {(textInput || textFile) && (
                        <Button variant="outline" onClick={clearTextInput}>
                          <X className="h-4 w-4" />
                        </Button>
                      )}
                    </div>

                    {/* Status Messages */}
                    {textStatus === "success" && (
                      <div className="flex items-center gap-2 text-green-600">
                        <CheckCircle className="h-4 w-4" />
                        <span className="text-sm">PII scanning completed successfully!</span>
                      </div>
                    )}

                    {textStatus === "error" && (
                      <div className="flex items-center gap-2 text-red-600">
                        <AlertCircle className="h-4 w-4" />
                        <span className="text-sm">Scanning failed. Please try again.</span>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Text Results Card */}
                {(redactedText || textProcessedData) && (
                  <motion.div
                    initial={{ opacity: 0, x: 50 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.4 }}
                  >
                    <Card>
                      <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                          <Info className="h-5 w-5" />
                          PII Detection Results
                        </CardTitle>
                        <CardDescription>
                          {textMessage}
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        {/* Redacted Text */}
                        {redactedText && (
                          <div>
                            <div className="flex items-center justify-between mb-2">
                              <h3 className="text-sm font-medium">Redacted Text:</h3>
                              <Button 
                                onClick={downloadRedactedText} 
                                variant="outline" 
                                size="sm"
                                className="flex items-center gap-2"
                              >
                                <Download className="h-4 w-4" />
                                Download
                              </Button>
                            </div>
                            <div className="bg-muted p-4 rounded-lg max-h-80 overflow-auto">
                              <pre className="whitespace-pre-wrap font-mono text-sm">{redactedText}</pre>
                            </div>
                          </div>
                        )}

                        {/* Processing Data */}
                        {textProcessedData && (
                          <div className="space-y-2">
                            <h3 className="text-sm font-medium">Analysis Information:</h3>
                            <div className="bg-muted p-3 rounded-lg text-sm space-y-1">
                              <p><span className="font-medium">Input Type:</span> {textProcessedData.input_type}</p>
                              <p><span className="font-medium">Status:</span> <span className="text-green-600 capitalize">{textProcessedData.processing_status}</span></p>
                            </div>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  </motion.div>
                )}
              </div>
            </motion.div>
          )}

          {activeTab === 'image' && (
            <motion.div
              key="image-tab"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.3 }}
            >
              <div className={`grid gap-6 ${processedImage || imageProcessedData ? "grid-cols-1 lg:grid-cols-2" : "grid-cols-1 place-items-center"}`}>
                {/* Image Input Card */}
                <Card className={`${processedImage || imageProcessedData ? "" : "max-w-2xl w-full"}`}>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Eye className="h-5 w-5" />
                      Visual Cues Detection
                    </CardTitle>
                    <CardDescription>
                      Upload an image to identify and mark visual cues, sensitive information, or objects of interest
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {/* File Input */}
                    <input 
                      ref={imageFileInputRef}
                      type="file" 
                      accept="image/*"
                      onChange={handleImageFileSelect} 
                      className="hidden" 
                      id="image-file-input" 
                    />
                    
                    {/* Drop Zone */}
                    <div 
                      className="border-2 border-dashed border-border rounded-lg p-8 text-center hover:border-ring transition-colors cursor-pointer"
                      onClick={() => imageFileInputRef.current?.click()}
                      onPaste={handleImagePaste}
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          imageFileInputRef.current?.click()
                        }
                      }}
                    >
                      {imagePreview ? (
                        <div className="relative">
                          <img
                            src={imagePreview}
                            alt="Preview"
                            className="max-h-64 mx-auto rounded-lg"
                          />
                          <Button 
                            variant="destructive" 
                            size="sm" 
                            className="absolute top-2 right-2" 
                            onClick={(e) => {
                              e.stopPropagation()
                              clearImageInput()
                            }}
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        </div>
                      ) : (
                        <div className="space-y-4">
                          <Upload className="h-12 w-12 mx-auto text-muted-foreground" />
                          <div>
                            <p className="text-lg font-medium">Click to upload an image</p>
                            <p className="text-sm text-muted-foreground mt-1">
                              or paste from clipboard (Ctrl+V)
                            </p>
                          </div>
                          <p className="text-xs text-muted-foreground">
                            Supported formats: JPEG, PNG, GIF, WebP
                          </p>
                        </div>
                      )}
                    </div>

                    {/* Action Buttons */}
                    <div className="flex gap-2">
                      <Button 
                        onClick={handleImageScan} 
                        disabled={!imageFile || imageUploading} 
                        className="flex-1"
                      >
                        <Eye className="h-4 w-4 mr-2" />
                        {imageUploading ? "Analyzing..." : "Identify Visual Cues"}
                      </Button>
                      
                      {imageFile && (
                        <Button variant="outline" onClick={clearImageInput}>
                          <X className="h-4 w-4" />
                        </Button>
                      )}
                    </div>

                    {/* Status Messages */}
                    {imageStatus === "success" && (
                      <div className="flex items-center gap-2 text-green-600">
                        <CheckCircle className="h-4 w-4" />
                        <span className="text-sm">Image analysis completed successfully!</span>
                      </div>
                    )}

                    {imageStatus === "error" && (
                      <div className="flex items-center gap-2 text-red-600">
                        <AlertCircle className="h-4 w-4" />
                        <span className="text-sm">Analysis failed. Please try again.</span>
                      </div>
                    )}
                  </CardContent>
                </Card>

                {/* Image Results Card */}
                {(processedImage || imageProcessedData) && (
                  <motion.div
                    initial={{ opacity: 0, x: 50 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.4 }}
                  >
                    <Card>
                      <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                          <Info className="h-5 w-5" />
                          Visual Analysis Results
                        </CardTitle>
                        <CardDescription>
                          {imageMessage}
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        {/* Processed Image */}
                        {processedImage && (
                          <div>
                            <div className="flex items-center justify-between mb-2">
                              <h3 className="text-sm font-medium">Processed Image:</h3>
                              <Button 
                                onClick={downloadProcessedImage} 
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
                              className="w-full max-h-96 object-contain rounded-lg border"
                            />
                          </div>
                        )}

                        {/* Processing Data */}
                        {imageProcessedData && (
                          <div className="space-y-2">
                            <h3 className="text-sm font-medium">Analysis Information:</h3>
                            <div className="bg-muted p-3 rounded-lg text-sm space-y-1">
                              {imageProcessedData.original_filename && (
                                <p><span className="font-medium">Filename:</span> {imageProcessedData.original_filename}</p>
                              )}
                              {imageProcessedData.image_size && (
                                <p><span className="font-medium">Dimensions:</span> {imageProcessedData.image_size.width} × {imageProcessedData.image_size.height}</p>
                              )}
                              {imageProcessedData.file_size && (
                                <p><span className="font-medium">File Size:</span> {(imageProcessedData.file_size / 1024).toFixed(2)} KB</p>
                              )}
                              {imageProcessedData.format && (
                                <p><span className="font-medium">Format:</span> {imageProcessedData.format}</p>
                              )}
                              {imageProcessedData.mode && (
                                <p><span className="font-medium">Color Mode:</span> {imageProcessedData.mode}</p>
                              )}
                              <p><span className="font-medium">Input Type:</span> {imageProcessedData.input_type}</p>
                              <p><span className="font-medium">Status:</span> <span className="text-green-600 capitalize">{imageProcessedData.processing_status}</span></p>
                            </div>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  </motion.div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}