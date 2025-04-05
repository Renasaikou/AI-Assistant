# -*- coding: utf-8 -*-
import os
import re
import time
import pyaudio
import wave
from faster_whisper import WhisperModel
import asyncio
import opencc
import torch
from edge_tts import Communicate
from playsound import playsound
import numpy as np
from PIL import ImageGrab
import base64
import requests
import json

# 初始化转换器，将繁体字转换为简体字
converter = opencc.OpenCC('t2s.json')  # t2s 表示繁体到简体

# 配置参数
RECORD_SECONDS = 5  # 每次录音时长（仅用于唤醒阶段）
WAVE_OUTPUT_FILENAME = "output.wav"  # 录音文件名
MODEL_PATH = "./faster-whisper-base"  # 模型路径
GLM_API_KEY = "05dfdb57375347c488d28bac780b581a.g9gDkxmAYWmGxhPn"  # 替换为你的智谱 GLM-4V-Flash API 密钥
TTS_NAME = "zh-CN-XiaoxiaoNeural"  # TTS 音色
TEMP_FOLDER = "temp"  # 临时文件夹名称
CLEANUP_INTERVAL = 6  # 每6秒清理一次最早的录音文件
FILE_IN_USE = set()  # 用于记录正在使用的文件
AUDIO_FILES = []  # 用于记录音频文件的路径
SCREENSHOT_FILES = []  # 用于记录截图文件的路径
TTS_FILES = []  # 用于记录 TTS 文件的路径
SILENCE_THRESHOLD = 0.17  # 音频输入阈值
SILENCE_DURATION = 3  # 静音持续时间（秒）

# 指定模型加载设备
device = "cpu"
print(f"Using device: {device}")  # 打印使用的设备

# 初始化本地faster-Whisper 模型
model = WhisperModel(MODEL_PATH, device=device, compute_type="int8", local_files_only=True)

# 创建临时文件夹
def create_temp_folder():
    if not os.path.exists(TEMP_FOLDER):
        os.makedirs(TEMP_FOLDER)

# 删除最早的文件
def delete_earliest_file(file_list):
    if file_list:
        earliest_file = file_list.pop(0)
        try:
            if os.path.isfile(earliest_file):
                os.remove(earliest_file)
                print(f"Deleted file: {earliest_file}")
        except Exception as e:
            print(f"Error deleting file {earliest_file}: {e}")

# 唤醒阶段的录音函数
def record_audio(file_name):
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000

    p = pyaudio.PyAudio()

    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    frames = []

    for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
        data = stream.read(CHUNK)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    p.terminate()

    wf = wave.open(file_name, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

# 问题阶段的录音函数
def record_question_audio(file_name, silence_threshold, silence_duration):
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    SILENCE_FRAMES = int(RATE / CHUNK * silence_duration)  # 计算静音持续时间对应的帧数
    silence_count = 0  # 用于记录连续静音的帧数

    p = pyaudio.PyAudio()

    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    frames = []

    while True:
        data = stream.read(CHUNK)
        frames.append(data)
        # 使用 numpy 计算音频能量
        np_data = np.frombuffer(data, dtype=np.int16)
        energy = np.mean(np.abs(np_data)) / 32767.0  # 归一化到 [-1, 1]
        if energy < silence_threshold:
            silence_count += 1
            if silence_count >= SILENCE_FRAMES:
                break
        else:
            silence_count = 0

    stream.stop_stream()
    stream.close()
    p.terminate()

    wf = wave.open(file_name, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

def clean_text(text):
    # 去除特殊字符、占位符和无关字符，这里可以根据需要添加更多字符
    text = re.sub(r'[✳\*\[\]\(\)\{\}\<\>\/\\\|\#＃]+', '', text)
    # 去除多余的空白字符
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# 智谱 GLM-4V-Flash API 调用函数
def call_glm_api(question, screenshot_path):

    api_key = GLM_API_KEY

    # 将本地图片转换为base64编码
    with open(screenshot_path, 'rb') as img_file:
        img_base = base64.b64encode(img_file.read()).decode('utf-8')

    # 构造请求数据
    data = {
        "model": "glm-4v-flash",  # 使用GLM-4V-Flash模型
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": question  # 提问内容
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": img_base  # 图片的base64编码
                        }
                    }
                ]
            }
        ]
    }

    # 设置请求头
    headers = {
        "Authorization": f"Bearer {api_key}",  # 添加Bearer认证
        "Content-Type": "application/json"
    }

    # 发送请求
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    response = requests.post(url, headers=headers, data=json.dumps(data))

    # 检查响应
    if response.status_code == 200:
        response_data = response.json()
        answer = response_data["choices"][0]["message"].get("content", "抱歉，我没有理解你的问题。")
        return answer
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
        return "抱歉，我没有理解你的问题。"

async def main():
    create_temp_folder()
    last_cleanup_time = time.time()
    while True:
        # 定期清理最早的录音文件
        current_time = time.time()
        if current_time - last_cleanup_time >= CLEANUP_INTERVAL:
            delete_earliest_file(AUDIO_FILES)
            last_cleanup_time = current_time

        # 唤醒阶段的录音
        audio_file_path = os.path.join(TEMP_FOLDER, WAVE_OUTPUT_FILENAME)
        record_audio(audio_file_path)
        AUDIO_FILES.append(audio_file_path)
        FILE_IN_USE.add(audio_file_path)

        # 语音识别
        segments, info = model.transcribe(audio_file_path, beam_size=5)
        recognized_text = ""
        for segment in segments:
            recognized_text += segment.text

        # 将识别到的文本转换为简体字
        simplified_text = converter.convert(recognized_text)
        print(f"Recognized text: {simplified_text}")  # 打印识别到的文本

        # 判断是否包含自定义的关键词 "助教在吗"
        if "助教在吗" in simplified_text:
            print("我在")

            # 使用 edge-tts 将 "我在" 转换为语音
            tts = Communicate("我在", voice=TTS_NAME)
            tts_file_path = os.path.join(TEMP_FOLDER, "response.mp3")
            await tts.save(tts_file_path)
            TTS_FILES.append(tts_file_path)
            FILE_IN_USE.add(tts_file_path)

            # 播放 TTS 文件
            try:
                playsound(tts_file_path)
            except Exception as e:
                print(f"播放音频时出错：{e}")

            # 进入问题回答阶段
            print("进入问题回答阶段...")

            # 问题阶段的录音
            question_audio_file_path = os.path.join(TEMP_FOLDER, "question_output.wav")
            record_question_audio(question_audio_file_path, SILENCE_THRESHOLD, SILENCE_DURATION)
            AUDIO_FILES.append(question_audio_file_path)
            FILE_IN_USE.add(question_audio_file_path)

            # 截屏
            print("开始截图...")
            screenshot_path = os.path.join(TEMP_FOLDER, "screenshot.png")
            ImageGrab.grab().save(screenshot_path)
            SCREENSHOT_FILES.append(screenshot_path)
            FILE_IN_USE.add(screenshot_path)
            print(f"截图已保存到：{screenshot_path}")

            # 识别问题
            question_segments, question_info = model.transcribe(question_audio_file_path, beam_size=5)
            question_text = ""
            for segment in question_segments:
                question_text += segment.text
            print(f"Question: {question_text}")  # 打印识别到的问题

            # 调用智谱 GLM-4V-Flash API
            answer = call_glm_api(question_text, screenshot_path)
            print(f"Answer from GLM: {answer}")  # 打印智谱的回答

            # 清洗回答文本
            cleaned_answer = clean_text(answer)

            # 使用 edge-tts 将清洗后的回答转换为语音
            tts = Communicate(cleaned_answer, voice=TTS_NAME)
            tts_file_path = os.path.join(TEMP_FOLDER, "answer.mp3")
            await tts.save(tts_file_path)
            TTS_FILES.append(tts_file_path)
            FILE_IN_USE.add(tts_file_path)

            # 播放 TTS 文件
            try:
                playsound(tts_file_path)
            except Exception as e:
                print(f"播放音频时出错：{e}")

            # 删除截图和 TTS 文件
            delete_earliest_file(SCREENSHOT_FILES)
            delete_earliest_file(TTS_FILES)

            # 从正在使用的文件集合中移除文件
            FILE_IN_USE.remove(audio_file_path)
            FILE_IN_USE.remove(screenshot_path)
            FILE_IN_USE.remove(question_audio_file_path)
            FILE_IN_USE.remove(tts_file_path)

            print("回答完毕，等待下一次触发...")

        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
